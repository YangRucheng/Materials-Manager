package xls

import (
	"encoding/binary"
	"fmt"
	"io"
	"unicode/utf16"
)

type boundsheet struct {
	Filepos uint32
	Type    byte
	Visible byte
	Name    byte
}

// WorkSheet in one WorkBook
type WorkSheet struct {
	bs   *boundsheet
	wb   *WorkBook
	Name string
	rows map[uint16]*Row
	//NOTICE: this is the max row number of the sheet, so it should be count -1
	MaxRow uint16
	parsed bool
	// pendingFormulaString 指向最近一个结果类型为字符串的 FORMULA 单元格；
	// 其缓存结果在紧随其后的 STRING(0x0207)/EXTSTRING(0x0803) 记录中。
	pendingFormulaString *FormulaCol
}

func (w *WorkSheet) Row(i int) *Row {
	row := w.rows[uint16(i)]
	if row == nil {
		// 稀疏行（无 ROW 记录）：原版在这里对 nil 赋值会直接 panic。
		return nil
	}
	row.wb = w.wb
	return row
}

func (w *WorkSheet) parse(buf io.ReadSeeker) {
	w.rows = make(map[uint16]*Row)
	b := new(bof)
	var bof_pre *bof
	for {
		if err := binary.Read(buf, binary.LittleEndian, b); err == nil {
			bof_pre = w.parseBof(buf, b, bof_pre)
			if b.Id == 0xa {
				break
			}
		} else {
			fmt.Println(err)
			break
		}
	}
	w.parsed = true
}

func (w *WorkSheet) parseBof(buf io.ReadSeeker, b *bof, pre *bof) *bof {
	var col interface{}
	switch b.Id {
	// case 0x0E5: //MERGEDCELLS
	// ws.mergedCells(buf)
	case 0x208: //ROW
		r := new(rowInfo)
		binary.Read(buf, binary.LittleEndian, r)
		w.addRow(r)
	case 0x0BD: //MULRK
		mc := new(MulrkCol)
		size := (b.Size - 6) / 6
		binary.Read(buf, binary.LittleEndian, &mc.Col)
		mc.Xfrks = make([]XfRk, size)
		for i := uint16(0); i < size; i++ {
			binary.Read(buf, binary.LittleEndian, &mc.Xfrks[i])
		}
		binary.Read(buf, binary.LittleEndian, &mc.LastColB)
		col = mc
	case 0x0BE: //MULBLANK
		mc := new(MulBlankCol)
		size := (b.Size - 6) / 2
		binary.Read(buf, binary.LittleEndian, &mc.Col)
		mc.Xfs = make([]uint16, size)
		for i := uint16(0); i < size; i++ {
			binary.Read(buf, binary.LittleEndian, &mc.Xfs[i])
		}
		binary.Read(buf, binary.LittleEndian, &mc.LastColB)
		col = mc
	case 0x203: //NUMBER
		col = new(NumberCol)
		binary.Read(buf, binary.LittleEndian, col)
	case 0x06: //FORMULA
		c := new(FormulaCol)
		binary.Read(buf, binary.LittleEndian, &c.Header)
		c.Bts = make([]byte, b.Size-20)
		binary.Read(buf, binary.LittleEndian, &c.Bts)
		col = c
		if c.resultIsString() {
			// BIFF8：字符串型公式的缓存结果在紧随其后的 STRING 记录（0x0207）里。
			w.pendingFormulaString = c
		} else {
			w.pendingFormulaString = nil
		}
	case 0x207: //STRING（公式缓存的字符串结果，必须紧跟 FORMULA）
		// 实际写手（Excel/WPS，依 xlrd 与 POI 的一致行为）：payload = Cch(2) + Option(1) + 字符；
		// 少数遵循 OOo 文档的写手把 Row/Col 放前面且无 Option 字节，作为兜底布局识别。
		payload := make([]byte, b.Size)
		if _, err := io.ReadFull(buf, payload); err != nil {
			break
		}
		if w.pendingFormulaString != nil {
			if str, ok := parseBiff8String(payload); ok {
				w.pendingFormulaString.RenderedValue = str
				w.pendingFormulaString = nil
			}
		}
	case 0x27e: //RK
		col = new(RkCol)
		binary.Read(buf, binary.LittleEndian, col)
	case 0xFD: //LABELSST
		col = new(LabelsstCol)
		binary.Read(buf, binary.LittleEndian, col)
	case 0x204:
		c := new(labelCol)
		binary.Read(buf, binary.LittleEndian, &c.BlankCol)
		var count uint16
		binary.Read(buf, binary.LittleEndian, &count)
		c.Str, _ = w.wb.get_string(buf, count)
		col = c
	case 0x201: //BLANK
		col = new(BlankCol)
		binary.Read(buf, binary.LittleEndian, col)
	case 0x1b8: //HYPERLINK
		var hy HyperLink
		binary.Read(buf, binary.LittleEndian, &hy.CellRange)
		buf.Seek(20, 1)
		var flag uint32
		binary.Read(buf, binary.LittleEndian, &flag)
		var count uint32

		if flag&0x14 != 0 {
			binary.Read(buf, binary.LittleEndian, &count)
			hy.Description = b.utf16String(buf, count)
		}
		if flag&0x80 != 0 {
			binary.Read(buf, binary.LittleEndian, &count)
			hy.TargetFrame = b.utf16String(buf, count)
		}
		if flag&0x1 != 0 {
			var guid [2]uint64
			binary.Read(buf, binary.BigEndian, &guid)
			if guid[0] == 0xE0C9EA79F9BACE11 && guid[1] == 0x8C8200AA004BA90B { //URL
				hy.IsUrl = true
				binary.Read(buf, binary.LittleEndian, &count)
				hy.Url = b.utf16String(buf, count/2)
			} else if guid[0] == 0x303000000000000 && guid[1] == 0xC000000000000046 { //URL{
				var upCount uint16
				binary.Read(buf, binary.LittleEndian, &upCount)
				binary.Read(buf, binary.LittleEndian, &count)
				bts := make([]byte, count)
				binary.Read(buf, binary.LittleEndian, &bts)
				hy.ShortedFilePath = string(bts)
				buf.Seek(24, 1)
				binary.Read(buf, binary.LittleEndian, &count)
				if count > 0 {
					binary.Read(buf, binary.LittleEndian, &count)
					buf.Seek(2, 1)
					hy.ExtendedFilePath = b.utf16String(buf, count/2+1)
				}
			}
		}
		if flag&0x8 != 0 {
			binary.Read(buf, binary.LittleEndian, &count)
			var bts = make([]uint16, count)
			binary.Read(buf, binary.LittleEndian, &bts)
			runes := utf16.Decode(bts[:len(bts)-1])
			hy.TextMark = string(runes)
		}

		w.addRange(&hy.CellRange, &hy)
	case 0x809:
		buf.Seek(int64(b.Size), 1)
	case 0xa:
	default:
		// log.Printf("Unknow %X,%d\n", b.Id, b.Size)
		buf.Seek(int64(b.Size), 1)
	}
	if col != nil {
		w.add(col)
	}
	return b
}

func (w *WorkSheet) add(content interface{}) {
	if ch, ok := content.(contentHandler); ok {
		if col, ok := content.(Coler); ok {
			w.addCell(col, ch)
		}
	}

}

func (w *WorkSheet) addCell(col Coler, ch contentHandler) {
	w.addContent(col.Row(), ch)
}

func (w *WorkSheet) addRange(rang Ranger, ch contentHandler) {

	for i := rang.FirstRow(); i <= rang.LastRow(); i++ {
		w.addContent(i, ch)
	}
}

func (w *WorkSheet) addContent(row_num uint16, ch contentHandler) {
	var row *Row
	var ok bool
	if row, ok = w.rows[row_num]; !ok {
		info := new(rowInfo)
		info.Index = row_num
		row = w.addRow(info)
	}
	row.cols[ch.FirstCol()] = ch
}

func (w *WorkSheet) addRow(info *rowInfo) (row *Row) {
	if info.Index > w.MaxRow {
		w.MaxRow = info.Index
	}
	var ok bool
	if row, ok = w.rows[info.Index]; ok {
		row.info = info
	} else {
		row = &Row{info: info, cols: make(map[uint16]contentHandler)}
		w.rows[info.Index] = row
	}
	return
}

// bytesToLatin1 把 BIFF8 STRING 记录中的 8 位字符序列按 Latin-1 转为 Go 字符串。
func bytesToLatin1(data []byte) string {
	runes := make([]rune, len(data))
	for i, v := range data {
		runes[i] = rune(v)
	}
	return string(runes)
}

// parseBiff8String 解析 STRING 记录 payload。已知两种布局，先 A 后 B 试探：
//
//	A) Excel/xlrd 实际行为：Cch(2) + Option(1) + 字符（Latin-1 或 UTF-16LE）；
//	B) OOo 文档布局：Row(2) + Col(2) + Cch(2) + 8 位字符（无 Option）。
//
// 都不成立则 ok=false，调用方保持空值且不偏移流位置。
func parseBiff8String(payload []byte) (string, bool) {
	decodeLatin := func(start, nchars int) string { return bytesToLatin1(payload[start : start+nchars]) }
	decodeUTF16 := func(start, nchars int) string {
		chars := make([]uint16, nchars)
		for i := 0; i < nchars; i++ {
			chars[i] = binary.LittleEndian.Uint16(payload[start+2*i:])
		}
		return string(utf16.Decode(chars))
	}
	// 先求「精确占满 payload」的布局，避免 B 的 Cch 被 A 的 Row 误判。
	if len(payload) >= 3 {
		nchars := int(binary.LittleEndian.Uint16(payload[:2]))
		if payload[2]&1 == 0 && 3+nchars == len(payload) {
			return decodeLatin(3, nchars), true
		}
		if payload[2]&1 == 1 && 3+2*nchars == len(payload) {
			return decodeUTF16(3, nchars), true
		}
	}
	if len(payload) >= 7 {
		if nchars := int(binary.LittleEndian.Uint16(payload[4:6])); 6+nchars == len(payload) {
			return decodeLatin(6, nchars), true
		}
	}
	// 兜底：允许 A 布局带尾部填充字节（个别写手补 \0）。
	if len(payload) >= 3 {
		nchars := int(binary.LittleEndian.Uint16(payload[:2]))
		if payload[2]&1 == 0 && 3+nchars <= len(payload) {
			return decodeLatin(3, nchars), true
		}
		if payload[2]&1 == 1 && 3+2*nchars <= len(payload) {
			return decodeUTF16(3, nchars), true
		}
	}
	return "", false
}
