package xls

import (
	"encoding/binary"
	"fmt"
	"math"
	"strconv"
)

// content type
type contentHandler interface {
	String(*WorkBook) []string
	FirstCol() uint16
	LastCol() uint16
}

type Col struct {
	RowB      uint16
	FirstColB uint16
}

type Coler interface {
	Row() uint16
}

func (c *Col) Row() uint16 {
	return c.RowB
}

func (c *Col) FirstCol() uint16 {
	return c.FirstColB
}

func (c *Col) LastCol() uint16 {
	return c.FirstColB
}

func (c *Col) String(wb *WorkBook) []string {
	return []string{"default"}
}

type XfRk struct {
	Index uint16
	Rk    RK
}

// String 渲染 RK 数值单元格。原版把所有用户自定义格式（fNo>=164）一律当日期、
// 输出 RFC3339 串（普通数字也变日期），内置日期格式又丢天；
// 此处改为按 XF 数字格式分类渲染（见 cell_format.go）。
func (xf *XfRk) String(wb *WorkBook) string {
	i, f, isFloat := xf.Rk.number()
	if !isFloat {
		f = float64(i)
	}
	return wb.formatNumberLikeCell(xf.Index, f, xf.Rk.String())
}

type RK uint32

// number 解码 RK 值（ECMA-376 2.4.1.84）。
// 原版把无符号右移结果直接当有符号整数（负数会解码成巨大正数），且忽略「整数值×100」组合。
func (rk RK) number() (intNum int64, floatNum float64, isFloat bool) {
	multiplied := rk & 1
	isInt := rk & 2
	if isInt == 0 {
		floatNum = math.Float64frombits(uint64(rk>>2) << 34)
		if multiplied != 0 {
			floatNum = floatNum / 100
		}
		return 0, floatNum, true
	}
	i := int32(rk) >> 2 // 30 位有符号整数：算术右移补符号
	if multiplied != 0 {
		return 0, float64(i) / 100, true
	}
	return int64(i), 0, false
}

func (rk RK) String() string {
	i, f, isFloat := rk.number()
	if isFloat {
		return strconv.FormatFloat(f, 'f', -1, 64)
	}
	return strconv.FormatInt(i, 10)
}

var ErrIsInt = fmt.Errorf("is int")

func (rk RK) Float() (float64, error) {
	_, f, isFloat := rk.number()
	if !isFloat {
		return 0, ErrIsInt
	}
	return f, nil
}

type MulrkCol struct {
	Col
	Xfrks    []XfRk
	LastColB uint16
}

func (c *MulrkCol) LastCol() uint16 {
	return c.LastColB
}

func (c *MulrkCol) String(wb *WorkBook) []string {
	var res = make([]string, len(c.Xfrks))
	for i := 0; i < len(c.Xfrks); i++ {
		xfrk := c.Xfrks[i]
		res[i] = xfrk.String(wb)
	}
	return res
}

type MulBlankCol struct {
	Col
	Xfs      []uint16
	LastColB uint16
}

func (c *MulBlankCol) LastCol() uint16 {
	return c.LastColB
}

func (c *MulBlankCol) String(wb *WorkBook) []string {
	return make([]string, len(c.Xfs))
}

type NumberCol struct {
	Col
	Index uint16
	Float float64
}

// String 渲染 NUMBER 单元格。原版完全忽略数字格式：
// 日期格式的单元格输出 Excel 序列值（如 "42680"），下游日期解析全部失败；
// 此处按 XF 数字格式分类渲染（见 cell_format.go）。
func (c *NumberCol) String(wb *WorkBook) []string {
	return []string{wb.formatNumberLikeCell(c.Index, c.Float, strconv.FormatFloat(c.Float, 'f', -1, 64))}
}

type FormulaCol struct {
	Header struct {
		Col
		IndexXf uint16
		Result  [8]byte
		Flags   uint16
		_       uint32
	}
	Bts []byte
	// RenderedValue 由 FORMULA 后紧跟的 STRING 记录（0x0207）填充（字符串型公式的缓存结果）。
	RenderedValue string
}

// 原版把 Col 嵌在命名结构体字段 Header 里，FirstCol/LastCol/Row 均未提升到
// FormulaCol 上，导致 worksheet.add 的类型断言永远失败、公式单元格被静默丢弃。
func (c *FormulaCol) Row() uint16      { return c.Header.RowB }
func (c *FormulaCol) FirstCol() uint16 { return c.Header.FirstColB }
func (c *FormulaCol) LastCol() uint16  { return c.Header.FirstColB }

// resultIsSpecial 判定公式缓存结果是否为「特殊类型」：依据 xlrd（原 Python 后端所用库）的
// 权威行为——结果字节 6-7 均为 0xFF 时 byte0 给出类型：0=字符串（值在后续 STRING 记录）、
// 1=布尔、2=错误、3=空串；否则整 8 字节即小端 double。
func (c *FormulaCol) resultIsSpecial() bool {
	res := c.Header.Result
	return res[6] == 0xFF && res[7] == 0xFF
}

func (c *FormulaCol) resultIsString() bool {
	return c.resultIsSpecial() && c.Header.Result[0] == 0x00
}

// String 解码公式的缓存计算结果（原版直接返回字面量 "FormulaCol"，数量列一旦是公式必然报错）。
// 数值缓存按 XF 数字格式二次渲染（如 =TODAY() 输出日期），与 Excel 打开时显示一致。
func (c *FormulaCol) String(wb *WorkBook) []string {
	res := c.Header.Result
	if c.resultIsSpecial() {
		switch res[0] {
		case 0x00: // 字符串：值由紧随的 STRING 记录填充
			return []string{c.RenderedValue}
		case 0x01: // 布尔
			if res[2] != 0 {
				return []string{"TRUE"}
			}
			return []string{"FALSE"}
		case 0x02: // 错误值
			return []string{"#ERROR"}
		default: // 0x03：空串
			return []string{""}
		}
	}
	f := math.Float64frombits(binary.LittleEndian.Uint64(res[:]))
	return []string{wb.formatNumberLikeCell(c.Header.IndexXf, f, strconv.FormatFloat(f, 'f', -1, 64))}
}

type RkCol struct {
	Col
	Xfrk XfRk
}

func (c *RkCol) String(wb *WorkBook) []string {
	return []string{c.Xfrk.String(wb)}
}

type LabelsstCol struct {
	Col
	Xf  uint16
	Sst uint32
}

func (c *LabelsstCol) String(wb *WorkBook) []string {
	return []string{wb.sst[int(c.Sst)]}
}

type labelCol struct {
	BlankCol
	Str string
}

func (c *labelCol) String(wb *WorkBook) []string {
	return []string{c.Str}
}

type BlankCol struct {
	Col
	Xf uint16
}

func (c *BlankCol) String(wb *WorkBook) []string {
	return []string{""}
}
