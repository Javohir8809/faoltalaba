FROM golang:1.25-alpine AS builder
ENV CGO_ENABLED=0 GOMAXPROCS=2 GOBIN=/out
# Official source release with the session-policy security fix. Go verifies module sums.
RUN go install -p 2 github.com/minio/minio@RELEASE.2025-10-15T17-29-55Z \
    && cp /go/pkg/mod/github.com/minio/minio@*/LICENSE /out/LICENSE

FROM alpine:3.22
RUN apk add --no-cache ca-certificates \
    && addgroup -S minio \
    && adduser -S -G minio minio \
    && mkdir /data \
    && chown minio:minio /data
COPY --from=builder /out/minio /usr/local/bin/minio
COPY --from=builder /out/LICENSE /licenses/minio-LICENSE
LABEL org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.version="RELEASE.2025-10-15T17-29-55Z" \
      org.opencontainers.image.licenses="AGPL-3.0-only"
USER minio
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
CMD ["server", "/data", "--console-address", ":9001"]
