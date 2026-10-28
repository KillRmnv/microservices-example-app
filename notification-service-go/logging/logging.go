// Package logging provides structured JSON logging, secret redaction,
// request-ID propagation and RFC 9457 Problem Details for the service's
// small HTTP surface.
package logging

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"time"
)

const problemBase = "https://dosug.example/problems"

// Setup configures the default slog logger: JSON lines with the service name.
// LOG_LEVEL overrides the level (default INFO), LOG_FORMAT=text selects text.
func Setup(service string) {
	level := slog.LevelInfo
	switch strings.ToUpper(os.Getenv("LOG_LEVEL")) {
	case "DEBUG":
		level = slog.LevelDebug
	case "WARN", "WARNING":
		level = slog.LevelWarn
	case "ERROR":
		level = slog.LevelError
	}
	base := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: level}))
	slog.SetDefault(base.With("service", service))
	if strings.ToLower(os.Getenv("LOG_FORMAT")) == "text" {
		slog.SetDefault(slog.New(slog.NewTextHandler(os.Stdout,
			&slog.HandlerOptions{Level: level})).With("service", service))
	}
}

type ctxKey struct{}

// NewRequestID generates a random hex request id.
func NewRequestID() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		return time.Now().UTC().Format("20060102150405.000000")
	}
	return hex.EncodeToString(b[:])
}

// RequestIDMiddleware reads/sets X-Request-ID, echoes it back, stores it in
// the request context and logs method/path/status/duration.
func RequestIDMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := strings.TrimSpace(r.Header.Get("X-Request-ID"))
		if id == "" {
			id = NewRequestID()
		}
		w.Header().Set("X-Request-ID", id)
		ctx := context.WithValue(r.Context(), ctxKey{}, id)
		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		start := time.Now()
		next.ServeHTTP(rec, r.WithContext(ctx))
		slog.Info("http request",
			"request_id", id,
			"method", r.Method,
			"path", r.URL.Path,
			"status", rec.status,
			"duration_ms", time.Since(start).Milliseconds(),
		)
	})
}

// RequestID returns the request id from the context, or "".
func RequestID(ctx context.Context) string {
	id, _ := ctx.Value(ctxKey{}).(string)
	return id
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(code int) {
	r.status = code
	r.ResponseWriter.WriteHeader(code)
}

// MaskEmail renders u***@domain so logs never carry full addresses.
func MaskEmail(email string) string {
	at := strings.Index(email, "@")
	if at <= 0 {
		return email
	}
	return email[:1] + "***@" + email[at+1:]
}

// Problem is an RFC 9457 error body.
type Problem struct {
	Type     string         `json:"type"`
	Title    string         `json:"title"`
	Status   int            `json:"status"`
	Detail   string         `json:"detail"`
	Instance string         `json:"instance"`
	Code     string         `json:"code"`
	TraceID  string         `json:"trace_id"`
	Errors   []ProblemField `json:"errors,omitempty"`
}

// ProblemField is a single field-level validation failure.
type ProblemField struct {
	Field   string `json:"field"`
	Code    string `json:"code"`
	Message string `json:"message"`
}

// WriteProblem writes an application/problem+json response. The trace id is
// the request id (context first, then the X-Request-ID header), generated
// when missing.
func WriteProblem(w http.ResponseWriter, r *http.Request, status int, code, detail string) {
	trace := RequestID(r.Context())
	if trace == "" {
		trace = strings.TrimSpace(r.Header.Get("X-Request-ID"))
	}
	if trace == "" {
		trace = NewRequestID()
	}
	title := http.StatusText(status)
	if title == "" {
		title = code
	}
	body, _ := json.Marshal(Problem{
		Type:     problemBase + "/" + code,
		Title:    title,
		Status:   status,
		Detail:   detail,
		Instance: r.URL.Path,
		Code:     code,
		TraceID:  trace,
	})
	w.Header().Set("Content-Type", "application/problem+json")
	w.Header().Set("X-Request-ID", trace)
	w.WriteHeader(status)
	_, _ = w.Write(body)
}
