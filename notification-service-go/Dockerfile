FROM golang:1.23-alpine AS builder

WORKDIR /workspace/go
COPY ./notification-service-go .

RUN go mod download && CGO_ENABLED=0 go build -o /notification-service-go .

FROM alpine:3.20
RUN apk --no-cache add ca-certificates
RUN addgroup -S appgroup && adduser -S -G appgroup appuser

WORKDIR /app
COPY --from=builder /notification-service-go .

USER appuser

EXPOSE 8083

ENTRYPOINT ["./notification-service-go"]
