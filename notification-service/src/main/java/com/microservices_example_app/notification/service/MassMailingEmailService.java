package com.microservices_example_app.notification.service;

import com.microservices_example_app.notification.dto.MassDeleteEventMailingEvent;
import com.microservices_example_app.notification.dto.MassUpdateEventMailingEvent;
import com.microservices_example_app.notification.dto.UserNotificationDto;
import com.microservices_example_app.notification.exceptions.EmailSendingException;
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
public class MassMailingEmailService {

    private final JavaMailSender mailSender;

    @Value("${spring.mail.username}")
    private String senderEmail;

    public void sendMassDeleteEventMailing(MassDeleteEventMailingEvent event) {
        log.info("Sending mass delete event emails: {} users, {} events, sourceService={}",
                event.getUsers().size(), event.getEvents().size(), event.getSourceService());

        for (UserNotificationDto user : event.getUsers()) {
            SimpleMailMessage message = new SimpleMailMessage();
            message.setFrom(senderEmail);
            message.setTo(user.getEmail());
            message.setSubject("Event cancellation notice");
            message.setText("""
                    Hello, %s!
                    
                    We regret to inform you that the following event(s) have been cancelled:
                    %s
                    
                    Your tickets will be refunded automatically.
                    
                    Best regards,
                    Microservices Example App
                    """.formatted(user.getUsername(), String.join("\n- ", event.getEvents())));

            send(message, "mass delete event", user.getEmail(), event.getSourceService());
        }
    }

    public void sendMassUpdateEventMailing(MassUpdateEventMailingEvent event) {
        log.info("Sending mass update event emails: {} users, {} events, sourceService={}",
                event.getUsers().size(), event.getEvents().size(), event.getSourceService());

        for (UserNotificationDto user : event.getUsers()) {
            SimpleMailMessage message = new SimpleMailMessage();
            message.setFrom(senderEmail);
            message.setTo(user.getEmail());
            message.setSubject("Event update notice");
            message.setText("""
                    Hello, %s!
                    
                    The following event(s) have been updated:
                    - %s
                    
                    Changes:
                    %s
                    
                    Best regards,
                    Microservices Example App
                    """.formatted(user.getUsername(), String.join("\n- ", event.getEvents()), event.getChangesDescription()));

            send(message, "mass update event", user.getEmail(), event.getSourceService());
        }
    }

    private void send(SimpleMailMessage message, String emailType, String recipientEmail, String sourceService) {
        try {
            mailSender.send(message);
            log.info("Email sent: type={}, recipient={}, sourceService={}",
                    emailType, recipientEmail, sourceService);
        } catch (MailException ex) {
            log.error("Failed to send email: type={}, recipient={}, sourceService={}, reason={}",
                    emailType, recipientEmail, sourceService, ex.getMessage(), ex);
            throw new EmailSendingException("Failed to send " + emailType + " email to " + recipientEmail, ex);
        }
    }
}