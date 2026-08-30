package email

import (
	"fmt"
	"log"
	"net/smtp"
	"strings"
	"sync"
)

type Config struct {
	Host     string
	Port     string
	Username string
	Password string
}

type Service struct {
	cfg           Config
	maxConcurrent int
}

func NewService(cfg Config) *Service {
	return &Service{cfg: cfg, maxConcurrent: 50}
}

func (s *Service) addr() string {
	return s.cfg.Host + ":" + s.cfg.Port
}

func (s *Service) auth() smtp.Auth {
	return smtp.PlainAuth("", s.cfg.Username, s.cfg.Password, s.cfg.Host)
}

func (s *Service) send(to, subject, body string) error {
	msg := []byte("From: " + s.cfg.Username + "\r\n" +
		"To: " + to + "\r\n" +
		"Subject: " + subject + "\r\n" +
		"MIME-Version: 1.0\r\n" +
		"Content-Type: text/plain; charset=\"utf-8\"\r\n" +
		"\r\n" +
		body + "\r\n")

	err := smtp.SendMail(s.addr(), s.auth(), s.cfg.Username, []string{to}, msg)
	if err != nil {
		log.Printf("Failed to send email to %s: %v", to, err)
		return fmt.Errorf("failed to send email to %s: %w", to, err)
	}
	log.Printf("Email sent: type=unknown, recipient=%s", to)
	return nil
}

func (s *Service) sendBatch(to []string, subject, body string) error {
	msg := []byte("From: " + s.cfg.Username + "\r\n" +
		"Subject: " + subject + "\r\n" +
		"MIME-Version: 1.0\r\n" +
		"Content-Type: text/plain; charset=\"utf-8\"\r\n" +
		"\r\n" +
		body + "\r\n")

	return smtp.SendMail(s.addr(), s.auth(), s.cfg.Username, to, msg)
}

func (s *Service) SendSuccessfulRegistrationEmail(email, username, sourceService string) {
	log.Printf("Sending successful registration email: email=%s, username=%s, sourceService=%s", email, username, sourceService)
	body := fmt.Sprintf("Hello, %s!\n\nYour registration was completed successfully.\n\nBest regards,\nMicroservices Example App\n", username)
	if err := s.send(email, "Registration successful", body); err != nil {
		log.Printf("Failed to send successful registration email to %s: %v", email, err)
	}
}

func (s *Service) SendBookingSuccessEmail(email, username, event, sourceService string) {
	log.Printf("Sending booking success email: email=%s, username=%s, sourceService=%s", email, username, sourceService)
	body := fmt.Sprintf("Hello, %s!\n\nYour %s booking was completed successfully.\n\nBest regards,\nMicroservices Example App\n", username, event)
	if err := s.send(email, "Booking confirmed", body); err != nil {
		log.Printf("Failed to send booking success email to %s: %v", email, err)
	}
}

func (s *Service) SendTicketRefundEmail(email, username, eventTitle, sourceService string) {
	log.Printf("Sending ticket refund email: email=%s, username=%s, eventTitle=%s, sourceService=%s", email, username, eventTitle, sourceService)
	body := fmt.Sprintf(`Hello, %s!

		Your ticket refund for the event "%s" was completed successfully.
		
		If the payment was already charged, the refund will be processed according to your payment provider's terms.
		
		Best regards,
		Microservices Example App
		`, username, eventTitle)
	if err := s.send(email, "Ticket refund confirmed", body); err != nil {
		log.Printf("Failed to send ticket refund email to %s: %v", email, err)
	}
}

func (s *Service) SendForgetPasswordEmail(email, resetURL, sourceService string) {
	log.Printf("Sending forgot password email: email=%s, sourceService=%s", email, sourceService)
	body := fmt.Sprintf(`Hello!

		We received a request to reset your password.
		To continue, open the link below:
		%s
		
		If this was not you, just ignore this email.
		
		Best regards,
		Microservices Example App
		`, resetURL)
	if err := s.send(email, "Password reset request", body); err != nil {
		log.Printf("Failed to send forgot password email to %s: %v", email, err)
	}
}

func (s *Service) SendUserDeletedEmail(email, username, sourceService string) {
	log.Printf("Sending user deleted email: email=%s, username=%s, sourceService=%s", email, username, sourceService)
	body := fmt.Sprintf(`Hello, %s!

		Your account has been deleted successfully.
		
		Best regards,
		Microservices Example App
		`, username)
	if err := s.send(email, "Account deleted", body); err != nil {
		log.Printf("Failed to send user deleted email to %s: %v", email, err)
	}
}

func (s *Service) SendUserUpdatedEmail(email, username, role, sourceService string) {
	log.Printf("Sending user updated email: email=%s, username=%s, role=%s, sourceService=%s", email, username, role, sourceService)
	body := fmt.Sprintf(`Hello, %s!

	Your account information has been updated.
	Your current role: %s
	
	Best regards,
	Microservices Example App
	`, username, role)
	if err := s.send(email, "Account updated", body); err != nil {
		log.Printf("Failed to send user updated email to %s: %v", email, err)
	}
}

func (s *Service) SendMassDeleteEventMailing(users []struct {
	Email    string
	Username string
}, events []string, sourceService string) {
	log.Printf("Sending mass delete event emails: %d users, %d events, sourceService=%s", len(users), len(events), sourceService)
	eventsText := strings.Join(events, "\n- ")

	var wg sync.WaitGroup
	sem := make(chan struct{}, s.maxConcurrent)

	for _, user := range users {
		wg.Add(1)
		go func(u struct{ Email, Username string }) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()

			body := fmt.Sprintf(`Hello, %s!

			We regret to inform you that the following event(s) have been cancelled:
			- %s
			
			Your tickets will be refunded automatically.
			
			Best regards,
			Microservices Example App
			`, u.Username, eventsText)
			if err := s.send(u.Email, "Event cancellation notice", body); err != nil {
				log.Printf("Failed to send mass delete email to %s: %v", u.Email, err)
			}
		}(user)
	}
	wg.Wait()
}

func (s *Service) SendMassUpdateEventMailing(users []struct {
	Email    string
	Username string
}, events []string, changesDescription, sourceService string) {
	log.Printf("Sending mass update event emails: %d users, %d events, sourceService=%s", len(users), len(events), sourceService)
	eventsText := strings.Join(events, "\n- ")

	var wg sync.WaitGroup
	sem := make(chan struct{}, s.maxConcurrent)

	for _, user := range users {
		wg.Add(1)
		go func(u struct{ Email, Username string }) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()

			body := fmt.Sprintf(`Hello, %s!

			The following event(s) have been updated:
			- %s
			
			Changes:
			%s
			
			Best regards,
			Microservices Example App
			`, u.Username, eventsText, changesDescription)
			if err := s.send(u.Email, "Event update notice", body); err != nil {
				log.Printf("Failed to send mass update email to %s: %v", u.Email, err)
			}
		}(user)
	}
	wg.Wait()
}
