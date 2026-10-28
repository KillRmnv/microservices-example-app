package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"notification-service-go/email"
	kafkamodule "notification-service-go/kafka"
	"notification-service-go/logging"

	"github.com/prometheus/client_golang/prometheus/promhttp"
)

func envOrDefault(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func main() {
	logging.Setup("notification-service-go")
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	brokersRaw := envOrDefault("SPRING_KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
	brokers := strings.Split(brokersRaw, ",")

	mailHost := envOrDefault("MAIL_HOST", "smtp.gmail.com")
	mailPort := envOrDefault("MAIL_PORT", "587")
	mailUser := os.Getenv("MAIL_USERNAME")
	mailPass := os.Getenv("MAIL_PASSWORD")

	emailSvc := email.NewService(email.Config{
		Host:     mailHost,
		Port:     mailPort,
		Username: mailUser,
		Password: mailPass,
	})

	topics := kafkamodule.Topics{
		Authentication: envOrDefault("NOTIFICATION_AUTHENTICATION_TOPIC", "notification.authentication"),
		Booking:        envOrDefault("NOTIFICATION_BOOKING_TOPIC", "notification.booking"),
		TicketRefund:   envOrDefault("TICKET_REFUND", "notification.refund"),
		UserLifecycle:  envOrDefault("NOTIFICATION_USER_LIFECYCLE_TOPIC", "notification.user-lifecycle"),
		MassMailing:    envOrDefault("NOTIFICATION_MASS_MAILING_TOPIC", "notification.mass-mailing"),
		ForgetPassword: envOrDefault("FORGET_PASSWORD", "notification.forget-password"),
	}

	consumerCfg := kafkamodule.ConsumerConfig{
		Brokers:      brokers,
		GroupID:      "notification-service-group",
		Topics:       topics,
		EmailService: emailSvc,
	}

	go consumerCfg.Start(ctx)

	mux := http.NewServeMux()
	mux.HandleFunc("/actuator/health", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", http.MethodGet)
			logging.WriteProblem(w, r, http.StatusMethodNotAllowed,
				"http_405", "Method not allowed")
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"UP"}`))
	})
	mux.Handle("/metrics", methodOnly(http.MethodGet, promhttp.Handler()))

	handler := logging.RequestIDMiddleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/actuator/health", "/metrics":
			mux.ServeHTTP(w, r)
		default:
			logging.WriteProblem(w, r, http.StatusNotFound,
				"http_404", "Not found")
		}
	}))

	addr := envOrDefault("NOTIFICATION_ADDRESS", "0.0.0.0") + ":" + envOrDefault("NOTIFICATION_PORT", "8083")
	server := &http.Server{
		Addr:              addr,
		Handler:           handler,
		ReadHeaderTimeout: 10 * time.Second,
	}

	go func() {
		slog.Info("notification service listening", "addr", addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("http server error", "err", err)
			os.Exit(1)
		}
	}()

	<-ctx.Done()
	shutdown, stop := context.WithTimeout(context.Background(), 10*time.Second)
	defer stop()
	if err := server.Shutdown(shutdown); err != nil {
		slog.Error("http shutdown error", "err", err)
	}
}

func methodOnly(method string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != method {
			w.Header().Set("Allow", method)
			logging.WriteProblem(w, r, http.StatusMethodNotAllowed,
				"http_405", "Method not allowed")
			return
		}
		next.ServeHTTP(w, r)
	})
}
