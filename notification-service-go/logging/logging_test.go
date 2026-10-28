package logging

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestMaskEmail(t *testing.T) {
	if got := MaskEmail("user@example.com"); got != "u***@example.com" {
		t.Fatalf("got %q", got)
	}
	if got := MaskEmail("no-email"); got != "no-email" {
		t.Fatalf("got %q", got)
	}
}

func TestWriteProblemShape(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/missing", nil)
	req.Header.Set("X-Request-ID", "req-1")
	rec := httptest.NewRecorder()
	WriteProblem(rec, req, http.StatusNotFound, "http_404", "Not found")

	res := rec.Result()
	if ct := res.Header.Get("Content-Type"); ct != "application/problem+json" {
		t.Fatalf("content type %q", ct)
	}
	if id := res.Header.Get("X-Request-ID"); id != "req-1" {
		t.Fatalf("request id %q", id)
	}
	var body Problem
	if err := json.NewDecoder(res.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	if body.Type != "https://dosug.example/problems/http_404" || body.Code != "http_404" {
		t.Fatalf("body %+v", body)
	}
	if body.Status != 404 || body.Instance != "/missing" || body.TraceID != "req-1" {
		t.Fatalf("body %+v", body)
	}
}

func TestRequestIDMiddlewareEchoes(t *testing.T) {
	var seen string
	next := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = RequestID(r.Context())
		w.WriteHeader(http.StatusNoContent)
	})
	req := httptest.NewRequest(http.MethodGet, "/actuator/health", nil)
	rec := httptest.NewRecorder()
	RequestIDMiddleware(next).ServeHTTP(rec, req)
	if seen == "" || rec.Header().Get("X-Request-ID") != seen {
		t.Fatalf("seen %q header %q", seen, rec.Header().Get("X-Request-ID"))
	}

	req = httptest.NewRequest(http.MethodGet, "/actuator/health", nil)
	req.Header.Set("X-Request-ID", "client-id")
	rec = httptest.NewRecorder()
	RequestIDMiddleware(next).ServeHTTP(rec, req)
	if seen != "client-id" {
		t.Fatalf("seen %q", seen)
	}
}

func TestRedactsNothingSensitiveByAccident(t *testing.T) {
	// Guard: problem writer must not echo query secrets into instance.
	req := httptest.NewRequest(http.MethodGet, "/x?key=SECRET", nil)
	rec := httptest.NewRecorder()
	WriteProblem(rec, req, http.StatusBadRequest, "validation_error", "bad")
	var body Problem
	if err := json.NewDecoder(rec.Result().Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	// Instance is the path only — net/http strips the query already.
	if strings.Contains(body.Instance, "SECRET") {
		t.Fatalf("instance leaks query: %q", body.Instance)
	}
}
