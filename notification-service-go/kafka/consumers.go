package kafka

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"notification-service-go/dto"
	"notification-service-go/email"

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
			log.Printf("Kafka read error: %v", err)
			continue
		}
		var event T
		if err := json.Unmarshal(msg.Value, &event); err != nil {
			log.Printf("Failed to unmarshal message on topic %s: %v", msg.Topic, err)
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
			log.Printf("Received successful registration event: email=%s, username=%s, sourceService=%s",
				e.Email, e.Username, e.SourceService)
			c.EmailService.SendSuccessfulRegistrationEmail(e.Email, e.Username, e.SourceService)
		})

	// notification.forget-password
	go consumeLoop(ctx, newReader(brokers, c.Topics.ForgetPassword, baseGroup),
		func(e dto.ForgetPasswordEvent) {
			log.Printf("Received forget password event: email=%s, sourceService=%s",
				e.Email, e.SourceService)
			c.EmailService.SendForgetPasswordEmail(e.Email, e.ResetURL, e.SourceService)
		})

	// notification.user-lifecycle (deleted)
	go consumeLoop(ctx, newReader(brokers, c.Topics.UserLifecycle, baseGroup+"-deleted"),
		func(e dto.UserDeletedEvent) {
			log.Printf("Received user deleted event: userId=%d, email=%s, username=%s, sourceService=%s",
				e.UserID, e.Email, e.Username, e.SourceService)
			c.EmailService.SendUserDeletedEmail(e.Email, e.Username, e.SourceService)
		})

	// notification.user-lifecycle (updated)
	go consumeLoop(ctx, newReader(brokers, c.Topics.UserLifecycle, baseGroup+"-updated"),
		func(e dto.UserUpdatedEvent) {
			log.Printf("Received user updated event: userId=%d, email=%s, username=%s, role=%s, sourceService=%s",
				e.UserID, e.Email, e.Username, e.Role, e.SourceService)
			c.EmailService.SendUserUpdatedEmail(e.Email, e.Username, e.Role, e.SourceService)
		})

	// notification.booking
	go consumeLoop(ctx, newReader(brokers, c.Topics.Booking, baseGroup),
		func(e dto.SuccessfulBookingEvent) {
			log.Printf("Received booking event: email=%s, username=%s, event=%s, sourceService=%s",
				e.Email, e.Username, e.Event, e.SourceService)
			c.EmailService.SendBookingSuccessEmail(e.Email, e.Username, e.Event, e.SourceService)
		})

	// notification.refund
	go consumeLoop(ctx, newReader(brokers, c.Topics.TicketRefund, baseGroup),
		func(e dto.TicketRefundEvent) {
			log.Printf("Refund booking event: email=%s, username=%s, event=%s, sourceService=%s",
				e.Email, e.Username, e.EventTitle, e.SourceService)
			c.EmailService.SendTicketRefundEmail(e.Email, e.Username, e.EventTitle, e.SourceService)
		})

	// notification.mass-mailing (delete)
	go consumeLoop(ctx, newReader(brokers, c.Topics.MassMailing, baseGroup+"-delete"),
		func(e dto.MassDeleteEventMailingEvent) {
			log.Printf("Received MassDeleteEventMailingEvent: %d users, sourceService=%s",
				len(e.Users), e.SourceService)
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
			log.Printf("Received MassUpdateEventMailingEvent: %d users, sourceService=%s",
				len(e.Users), e.SourceService)
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

	log.Printf("Started 8 Kafka consumers on topics: %s",
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
	fmt.Println("Shutting down Kafka consumers...")
}
