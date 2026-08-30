package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"notification-service-go/email"
	kafkamodule "notification-service-go/kafka"
)

func envOrDefault(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func main() {
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

	consumerCfg.Start(ctx)

	addr := envOrDefault("NOTIFICATION_ADDRESS", "0.0.0.0") + ":" + envOrDefault("NOTIFICATION_PORT", "8083")
	http.HandleFunc("/actuator/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"UP"}`))
	})

	log.Printf("Notification service (Go) listening on %s", addr)
	if err := http.ListenAndServe(addr, nil); err != nil && err != http.ErrServerClosed {
		log.Fatalf("HTTP server error: %v", err)
	}
}
