# 阶段一：构建 Go 后端
FROM golang:1.27-alpine AS builder
ARG BUILD_TIME
ARG GIT_SHA
RUN apk add --no-cache gcc musl-dev libwebp-dev
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=1 GOOS=linux go build -ldflags "-s -w" \
    -o /out/server ./cmd/server

# 阶段二：运行镜像
FROM alpine:3.21
# libwebp：CGO 动态链接的 WebP 预览编解码库（构建期已链接，运行期需同版本运行库）
RUN apk add --no-cache ca-certificates tzdata libwebp
WORKDIR /app
COPY --from=builder /out/server /app/server
COPY templates /app/templates
COPY internal/openapi/openapi.yaml /app/openapi.yaml
ENV APP_ENVIRONMENT=production \
    APP_UPLOAD_DIR=/app/data/uploads \
    APP_LOG_DIR=/app/data/logs \
    APP_TEMPLATE_DIR=/app/templates \
    APP_BUILD_TIME=$BUILD_TIME \
    APP_GIT_SHA=$GIT_SHA
RUN mkdir -p /app/data/uploads /app/data/logs
EXPOSE 8000
ENTRYPOINT ["/app/server"]
