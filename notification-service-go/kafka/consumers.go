package kafka

import (
	"context"
	"encoding/json"
	"log/slog"
	"strings"
	"sync"
	"time"

	"notification-service-go/dto"
	"notification-service-go/email"
	"notification-service-go/logging"

	"github.com/segmentio/kafka-go"
)

type Topics struct {
	Authentication string
	Booking        string
	TicketRefund   string
	UserLifecycle  string
	MassMailing    string
	ForgetPassword string
}

type ConsumerConfig struct {
	Brokers      []string
	GroupID      string
	Topics       Topics
	EmailService *email.Service
}

func newReader(brokers []string, topic, groupID string) *kafka.Reader {
	return kafka.NewReader(kafka.ReaderConfig{
		Brokers:        brokers,
		Topic:          topic,
		GroupID:        groupID,
		MinBytes:       1,
		MaxBytes:       10e6,
		CommitInterval: time.Second,
		StartOffset:    kafka.FirstOffset,
	})
}

func consumeLoop[T any](ctx context.Context, r *kafka.Reader, handler func(T)) {
	defer r.Close()
	for {
		msg, err := r.ReadMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			slog.Warn("kafka read error", "err", err)
			continue
		}
		var event T
		if err := json.Unmarshal(msg.Value, &event); err != nil {
			slog.Warn("kafka unmarshal failed", "topic", msg.Topic, "err", err)
			continue
		}
		handler(event)
	}
}

func (c *ConsumerConfig) Start(ctx context.Context) {
	brokers := c.Brokers
	baseGroup := c.GroupID

	// notification.authentication
	go consumeLoop(ctx, newReader(brokers, c.Topics.Authentication, baseGroup),
		func(e dto.SuccessfulRegistrationEmailEvent) {
			slog.Info("registration event", "email", logging.MaskEmail(e.Email),
				"username", e.Username, "source", e.SourceService)
			c.EmailService.SendSuccessfulRegistrationEmail(e.Email, e.Username, e.SourceService)
		})

	// notification.forget-password
	go consumeLoop(ctx, newReader(brokers, c.Topics.ForgetPassword, baseGroup),
		func(e dto.ForgetPasswordEvent) {
			slog.Info("forget-password event", "email", logging.MaskEmail(e.Email),
				"source", e.SourceService)
			c.EmailService.SendForgetPasswordEmail(e.Email, e.ResetURL, e.SourceService)
		})

	// notification.user-lifecycle (deleted)
	go consumeLoop(ctx, newReader(brokers, c.Topics.UserLifecycle, baseGroup+"-deleted"),
		func(e dto.UserDeletedEvent) {
			slog.Info("user deleted event", "user_id", e.UserID,
				"email", logging.MaskEmail(e.Email), "username", e.Username,
				"source", e.SourceService)
			c.EmailService.SendUserDeletedEmail(e.Email, e.Username, e.SourceService)
		})

	// notification.user-lifecycle (updated)
	go consumeLoop(ctx, newReader(brokers, c.Topics.UserLifecycle, baseGroup+"-updated"),
		func(e dto.UserUpdatedEvent) {
			slog.Info("user updated event", "user_id", e.UserID,
				"email", logging.MaskEmail(e.Email), "username", e.Username,
				"role", e.Role, "source", e.SourceService)
			c.EmailService.SendUserUpdatedEmail(e.Email, e.Username, e.Role, e.SourceService)
		})

	// notification.booking
	go consumeLoop(ctx, newReader(brokers, c.Topics.Booking, baseGroup),
		func(e dto.SuccessfulBookingEvent) {
			slog.Info("booking event", "email", logging.MaskEmail(e.Email),
				"username", e.Username, "event", e.Event, "source", e.SourceService)
			c.EmailService.SendBookingSuccessEmail(e.Email, e.Username, e.Event, e.SourceService)
		})

	// notification.refund
	go consumeLoop(ctx, newReader(brokers, c.Topics.TicketRefund, baseGroup),
		func(e dto.TicketRefundEvent) {
			slog.Info("refund event", "email", logging.MaskEmail(e.Email),
				"username", e.Username, "event", e.EventTitle, "source", e.SourceService)
			c.EmailService.SendTicketRefundEmail(e.Email, e.Username, e.EventTitle, e.SourceService)
		})

	// notification.mass-mailing (delete)
	go consumeLoop(ctx, newReader(brokers, c.Topics.MassMailing, baseGroup+"-delete"),
		func(e dto.MassDeleteEventMailingEvent) {
			slog.Info("mass delete mailing", "users", len(e.Users),
				"source", e.SourceService)
			users := make([]struct {
				Email    string
				Username string
			}, len(e.Users))
			var wg sync.WaitGroup
			sem := make(chan struct{}, 50)
			for i, u := range e.Users {
				wg.Add(1)
				go func(idx int, du dto.UserNotificationDto) {
					defer wg.Done()
					sem <- struct{}{}
					defer func() { <-sem }()
					users[idx] = struct {
						Email    string
						Username string
					}{Email: du.Email, Username: du.Username}
				}(i, u)
			}
			wg.Wait()
			c.EmailService.SendMassDeleteEventMailing(users, e.Events, e.SourceService)
		})

	// notification.mass-mailing (update)
	go consumeLoop(ctx, newReader(brokers, c.Topics.MassMailing, baseGroup+"-update"),
		func(e dto.MassUpdateEventMailingEvent) {
			slog.Info("mass update mailing", "users", len(e.Users),
				"source", e.SourceService)
			users := make([]struct {
				Email    string
				Username string
			}, len(e.Users))
			var wg sync.WaitGroup
			sem := make(chan struct{}, 50)
			for i, u := range e.Users {
				wg.Add(1)
				go func(idx int, du dto.UserNotificationDto) {
					defer wg.Done()
					sem <- struct{}{}
					defer func() { <-sem }()
					users[idx] = struct {
						Email    string
						Username string
					}{Email: du.Email, Username: du.Username}
				}(i, u)
			}
			wg.Wait()
			c.EmailService.SendMassUpdateEventMailing(users, e.Events, e.ChangesDescription, e.SourceService)
		})

	slog.Info("kafka consumers started", "topics",
		strings.Join([]string{
			c.Topics.Authentication,
			c.Topics.ForgetPassword,
			c.Topics.UserLifecycle + " (deleted)",
			c.Topics.UserLifecycle + " (updated)",
			c.Topics.Booking,
			c.Topics.TicketRefund,
			c.Topics.MassMailing + " (delete)",
			c.Topics.MassMailing + " (update)",
		}, ", "))

	<-ctx.Done()
	slog.Info("shutting down kafka consumers")
}
