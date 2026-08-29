package database

import (
	"errors"
	"net/http"
	"strings"

	"github.com/go-sql-driver/mysql"
	"gorm.io/gorm"

	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
)

// MySQL 查询类错误码（等价 exception_handlers.MYSQL_QUERY_ERROR_CODES）。
var mysqlQueryErrorCodes = map[uint16]bool{
	1052: true, // Column is ambiguous
	1054: true, // Unknown column
	1064: true, // SQL syntax error
	1066: true, // Duplicate table alias
	1109: true, // Unknown table
	1146: true, // Table does not exist
}

// IsDuplicateError 判断唯一约束/外键约束冲突（MySQL 1062/1451/1452，SQLite 约束消息）。
func IsDuplicateError(err error) bool {
	if err == nil {
		return false
	}
	var myErr *mysql.MySQLError
	if errors.As(err, &myErr) {
		return myErr.Number == 1062 || myErr.Number == 1451 || myErr.Number == 1452
	}
	msg := err.Error()
	return strings.Contains(msg, "UNIQUE constraint failed") ||
		strings.Contains(msg, "FOREIGN KEY constraint failed") ||
		strings.Contains(msg, "constraint failed") ||
		strings.Contains(msg, "Duplicate entry")
}

// IsQueryError 判断数据库查询级错误（SQL 语法/字段缺失等 -> 500 DATABASE_QUERY_ERROR）。
func IsQueryError(err error) bool {
	if err == nil {
		return false
	}
	var myErr *mysql.MySQLError
	if errors.As(err, &myErr) {
		return mysqlQueryErrorCodes[myErr.Number]
	}
	return false
}

// IsUnavailableError 判断连接类错误（-> 503 DATABASE_UNAVAILABLE）。
func IsUnavailableError(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, gorm.ErrInvalidDB) || errors.Is(err, gorm.ErrInvalidTransaction) {
		return true
	}
	var myErr *mysql.MySQLError
	if errors.As(err, &myErr) {
		return myErr.Number == 1045 || myErr.Number == 2002 || myErr.Number == 2003 ||
			myErr.Number == 2006 || myErr.Number == 2013
	}
	msg := err.Error()
	return strings.Contains(msg, "connection refused") ||
		strings.Contains(msg, "connection reset") ||
		strings.Contains(msg, "broken pipe") ||
		strings.Contains(msg, "database is locked") ||
		strings.Contains(msg, "no such table")
}

// MapDBError 把 GORM 返回的错误映射为统一业务错误（等价 Python exception_handlers）。
func MapDBError(err error) *apperrors.AppError {
	if err == nil {
		return nil
	}
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return apperrors.NotFound("资源")
	}
	if IsDuplicateError(err) {
		return apperrors.New("DATA_CONFLICT", "数据约束冲突", http.StatusConflict, nil)
	}
	if IsQueryError(err) {
		return apperrors.New("DATABASE_QUERY_ERROR", "数据库查询执行失败，请联系管理员",
			http.StatusInternalServerError, nil)
	}
	if IsUnavailableError(err) {
		return apperrors.New("DATABASE_UNAVAILABLE", "数据库暂时不可用，请稍后重试",
			http.StatusServiceUnavailable, nil)
	}
	return apperrors.New("DATABASE_ERROR", "数据库操作失败，请联系管理员",
		http.StatusInternalServerError, nil)
}
