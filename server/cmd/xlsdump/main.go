// xlsdump 是一个诊断工具：不依赖表头对齐，按原始列号 dump 表格前 N 行的每个单元格
// （含类型与不可见字符转义），用于远程定位导入解析问题。
// 用法: go run ./cmd/xlsdump <文件路径> [行数]
package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"unicode"

	"github.com/yangrucheng/materials-manager/server/internal/excel"
)

func esc(s string) string {
	var b strings.Builder
	for _, r := range s {
		switch {
		case r == '\n':
			b.WriteString(`\n`)
		case r == '\t':
			b.WriteString(`\t`)
		case r == '\u00a0':
			b.WriteString(`\xa0`)
		case r == '\u3000':
			b.WriteString(`\u3000`)
		case !unicode.IsPrint(r):
			b.WriteString(fmt.Sprintf(`\x{%X}`, r))
		default:
			b.WriteRune(r)
		}
	}
	return b.String()
}

func main() {
	path := os.Args[1]
	limit := 6
	if len(os.Args) > 2 {
		limit, _ = strconv.Atoi(os.Args[2])
	}
	rows, appErr := excel.ReadTabularRows(path)
	if appErr != nil {
		fmt.Println("READ ERROR:", appErr.Code, appErr.Message)
		os.Exit(1)
	}
	fmt.Printf("file=%s totalRows=%d\n", path, len(rows))
	for i := 0; i < len(rows) && i < limit; i++ {
		fmt.Printf("--- 第%d行 (index=%d, cells=%d)\n", i+1, i, len(rows[i]))
		for j, cell := range rows[i] {
			s := fmt.Sprint(cell)
			if strings.TrimSpace(s) == "" {
				continue
			}
			fmt.Printf("  col[%d] type=%T value=%q\n", j, cell, esc(s))
		}
	}
}
