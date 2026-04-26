package com.microservices_example_app.notification.service;

import com.microservices_example_app.notification.dto.ForgetPasswordEvent;
import com.microservices_example_app.notification.dto.SuccessfulBookingEvent;
import com.microservices_example_app.notification.dto.SuccessfulRegistrationEmailEvent;
import com.microservices_example_app.notification.dto.TicketRefundEvent;
import com.microservices_example_app.notification.exceptions.EmailSendingException;
import lombok.AllArgsConstructor;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.MailException;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class EmailService {

    private final JavaMailSender mailSender;

    @Value("${spring.mail.username}")
    private String senderEmail;
    public void sendTicketRefundEmail(TicketRefundEvent event) {
        log.info("Sending ticket refund email: email={}, username={}, eventTitle={}, sourceService={}",
                event.getEmail(), event.getUsername(), event.getEventTitle(), event.getSourceService());

        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(senderEmail);
        message.setTo(event.getEmail());
        message.setSubject("Ticket refund confirmed");
        message.setText("""
            Hello, %s!
            
            Your ticket refund for the event "%s" was completed successfully.
            
            If the payment was already charged, the refund will be processed according to your payment provider's terms.
            
            Best regards,
            Microservices Example App
            """.formatted(event.getUsername(), event.getEventTitle()));

        send(message, "ticket refund", event.getEmail(), event.getSourceService());
    }
    public void sendBookingSuccessEmail(SuccessfulBookingEvent event) {
        log.info("Sending booking success email: email={}, username={}, sourceService={}",
                event.getEmail(), event.getUsername(), event.getSourceService());

        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(senderEmail);
        message.setTo(event.getEmail());
        message.setSubject("Booking confirmed");
        message.setText("""
                Hello, %s!
                
                Your booking was completed successfully.
                
                Best regards,
                Microservices Example App
                """.formatted(event.getUsername()));

        send(message, "booking success", event.getEmail(), event.getSourceService());
    }

    public void sendSuccessfulRegistrationEmail(SuccessfulRegistrationEmailEvent event) {
        log.info("Sending successful registration email: email={}, username={}, sourceService={}",
                event.getEmail(), event.getUsername(), event.getSourceService());

        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(senderEmail);
        message.setTo(event.getEmail());
        message.setSubject("Registration successful");
        message.setText("""
                Hello, %s!
                
                Your registration was completed successfully.
                
                Best regards,
                Microservices Example App
                """.formatted(event.getUsername()));

        send(message, "successful registration", event.getEmail(), event.getSourceService());
    }

    public void sendForgetPasswordEmail(ForgetPasswordEvent event) {
        log.info("Sending forgot password email: email={}, sourceService={}",
                event.getEmail(), event.getSourceService());

        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(senderEmail);
        message.setTo(event.getEmail());
        message.setSubject("Password reset request");
        message.setText("""
            Hello!
            
            We received a request to reset your password.
            To continue, open the link below:
            %s
            
            If this was not you, just ignore this email.
            
            Best regards,
            Microservices Example App
            """.formatted(event.getResetUrl()));

        send(message, "forgot password", event.getEmail(), event.getSourceService());
    }

    private void send(SimpleMailMessage message, String emailType, String recipientEmail, String sourceService) {
        try {
            mailSender.send(message);
            log.info("Email sent successfully: type={}, recipient={}, sourceService={}",
                    emailType, recipientEmail, sourceService);
        } catch (MailException ex) {
            log.error("Failed to send email: type={}, recipient={}, sourceService={}, reason={}",
                    emailType, recipientEmail, sourceService, ex.getMessage(), ex);
            throw new EmailSendingException("Failed to send " + emailType + " email to " + recipientEmail, ex);
        }
    }
}