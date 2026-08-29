// Package models 定义与 MySQL schema（example/database/init.sql）一致的 GORM 模型。
// 枚举列在 DB 中存枚举 NAME（如 'SUPER_ADMIN'/'NORMAL'）；API 层负责 NAME↔VALUE 转换
// （如 PurchasePlanStatus 的 VALUE 为中文）。
package models

import (
	"database/sql/driver"
	"fmt"
	"time"

	"github.com/shopspring/decimal"
	"gorm.io/datatypes"
	"gorm.io/gorm"
)

// Decimal 兼容 DECIMAL(p,s) 列的值类型（Value 输出规范字符串，Scan 解析）。
type Decimal struct {
	decimal.Decimal
}

func NewDecimal(v string) Decimal {
	d, err := decimal.NewFromString(v)
	if err != nil {
		return Decimal{Decimal: decimal.Zero}
	}
	return Decimal{Decimal: d}
}

func (d Decimal) Value() (driver.Value, error) {
	return d.Decimal.String(), nil
}

func (d *Decimal) Scan(v any) error {
	switch src := v.(type) {
	case nil:
		d.Decimal = decimal.Zero
		return nil
	case []byte:
		dec, err := decimal.NewFromString(string(src))
		if err != nil {
			return err
		}
		d.Decimal = dec
		return nil
	case string:
		dec, err := decimal.NewFromString(src)
		if err != nil {
			return err
		}
		d.Decimal = dec
		return nil
	case float64:
		d.Decimal = decimal.NewFromFloat(src)
		return nil
	default:
		return fmt.Errorf("无法扫描 Decimal: %T", v)
	}
}

func (d *Decimal) GormDataType() string { return "decimal" }

// Audit 提供 created_at / updated_at / version 字段（对应 Python AuditMixin）。
type Audit struct {
	CreatedAt time.Time `json:"created_at" gorm:"type:datetime;not null"`
	UpdatedAt time.Time `json:"updated_at" gorm:"type:datetime;not null"`
	Version   int       `json:"version" gorm:"type:int unsigned;not null;default:1"`
}

func (a *Audit) BeforeCreate(tx *gorm.DB) error {
	now := time.Now().UTC()
	if a.CreatedAt.IsZero() {
		a.CreatedAt = now
	}
	if a.UpdatedAt.IsZero() {
		a.UpdatedAt = now
	}
	if a.Version == 0 {
		a.Version = 1
	}
	return nil
}

func (a *Audit) BeforeUpdate(tx *gorm.DB) error {
	a.UpdatedAt = time.Now().UTC()
	return nil
}

// JSON 别名：datatypes.JSON 的快捷方式。
type JSON = datatypes.JSON

// UTCNow 返回当前 UTC 时间。
func UTCNow() time.Time { return time.Now().UTC() }
