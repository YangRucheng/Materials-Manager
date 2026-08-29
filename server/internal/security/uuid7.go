package security

import (
	"crypto/rand"
	"encoding/binary"
	"sync"
	"time"
)

// UUIDv7 生成单调递增的 UUIDv7（复刻 backend/app/core/identifiers.py 的布局）。
var (
	uuid7Mu       sync.Mutex
	uuid7LastMs   int64 = -1
	uuid7LastRand uint64
	uuid7RandBits = 74
	uuid7RandMask = (uint64(1) << uuid7RandBits) - 1
)

// UUID7String 返回规范小写 UUIDv7 字符串。
func UUID7String() string {
	uuid7Mu.Lock()
	defer uuid7Mu.Unlock()

	now := time.Now().UnixMilli()
	var random uint64
	if now > uuid7LastMs {
		random = cryptoRand64() & uuid7RandMask
	} else {
		now = uuid7LastMs
		random = (uuid7LastRand + 1) & uuid7RandMask
		if random == 0 {
			now++
		}
	}
	uuid7LastMs = now
	uuid7LastRand = random

	randomA := random >> 62 // 12 bits
	randomB := random & ((uint64(1) << 62) - 1)

	var b [16]byte
	// 48-bit 毫秒时间戳 -> bytes 0-5
	b[0] = byte(now >> 40)
	b[1] = byte(now >> 32)
	b[2] = byte(now >> 24)
	b[3] = byte(now >> 16)
	b[4] = byte(now >> 8)
	b[5] = byte(now)
	// version 7 + random_a 高 4 位
	b[6] = 0x70 | byte((randomA>>8)&0x0f)
	// random_a 低 8 位
	b[7] = byte(randomA & 0xff)
	// variant 10 + random_b 高 6 位
	b[8] = 0x80 | byte((randomB>>56)&0x3f)
	// random_b 剩余 56 位
	b[9] = byte(randomB >> 48)
	b[10] = byte(randomB >> 40)
	b[11] = byte(randomB >> 32)
	b[12] = byte(randomB >> 24)
	b[13] = byte(randomB >> 16)
	b[14] = byte(randomB >> 8)
	b[15] = byte(randomB)

	const hexDigits = "0123456789abcdef"
	out := make([]byte, 36)
	pos := 0
	for i := 0; i < 16; i++ {
		if i == 4 || i == 6 || i == 8 || i == 10 {
			out[pos] = '-'
			pos++
		}
		out[pos] = hexDigits[b[i]>>4]
		out[pos+1] = hexDigits[b[i]&0x0f]
		pos += 2
	}
	return string(out)
}

func cryptoRand64() uint64 {
	var buf [8]byte
	if _, err := rand.Read(buf[:]); err != nil {
		return uint64(time.Now().UnixNano())
	}
	return binary.BigEndian.Uint64(buf[:])
}
