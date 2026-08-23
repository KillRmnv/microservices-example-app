package com.microservices_example_app.notification.service;

import com.microservices_example_app.notification.dto.MassDeleteEventMailingEvent;
import com.microservices_example_app.notification.dto.MassUpdateEventMailingEvent;
import com.microservices_example_app.notification.exceptions.EmailSendingException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.MailException;
import org.springframework.mail.MailSendException;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.stream.IntStream;

@Slf4j
@Service
@RequiredArgsConstructor
public class MassMailingEmailService {

    private final JavaMailSender mailSender;

    @Value("${spring.mail.username}")
    private String senderEmail;

    @Value("${notification.email.batch-size:50}")
    private int batchSize;

    public void sendMassDeleteEventMailing(MassDeleteEventMailingEvent event) {
        log.info("Sending mass delete event emails: {} users, {} events, sourceService={}",
                event.getUsers().size(), event.getEvents().size(), event.getSourceService());

        String eventsText = String.join("\n- ", event.getEvents());

        SimpleMailMessage[] messages = event.getUsers().parallelStream()
                .map(user -> {
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
                            """.formatted(user.getUsername(), eventsText));
                    return message;
                })
                .toArray(SimpleMailMessage[]::new);

        sendBatch(messages, "mass delete event", event.getSourceService());
    }

    public void sendMassUpdateEventMailing(MassUpdateEventMailingEvent event) {
        log.info("Sending mass update event emails: {} users, {} events, sourceService={}",
                event.getUsers().size(), event.getEvents().size(), event.getSourceService());

        String eventsText = String.join("\n- ", event.getEvents());

        SimpleMailMessage[] messages = event.getUsers().parallelStream()
                .map(user -> {
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
                            """.formatted(user.getUsername(), eventsText, event.getChangesDescription()));
                    return message;
                })
                .toArray(SimpleMailMessage[]::new);

        sendBatch(messages, "mass update event", event.getSourceService());
    }

    private void sendBatch(SimpleMailMessage[] messages, String emailType, String sourceService) {
        int totalBatches = (messages.length + batchSize - 1) / batchSize;

        IntStream.range(0, totalBatches).parallel().forEach(batchIndex -> {
            int start = batchIndex * batchSize;
            int end = Math.min(start + batchSize, messages.length);
            SimpleMailMessage[] batch = Arrays.copyOfRange(messages, start, end);

            try {
                mailSender.send(batch);
                log.info("Batch sent: type={}, batch={}/{}, recipients={}, sourceService={}",
                        emailType, batchIndex + 1, totalBatches, batch.length, sourceService);
            } catch (MailSendException ex) {
                log.error("Failed to send batch: type={}, batch={}/{},  sourceService={}, reason={}",
                        emailType, batchIndex + 1, totalBatches, sourceService, ex.getMessage(), ex);
                throw new EmailSendingException("Failed to send " + emailType + " batch " + (batchIndex + 1) + "/" + totalBatches, ex);
            } catch (MailException ex) {
                log.error("Failed to send batch: type={}, batch={}/{}, sourceService={}, reason={}",
                        emailType, batchIndex + 1, totalBatches, sourceService, ex.getMessage(), ex);
                throw new EmailSendingException("Failed to send " + emailType + " batch " + (batchIndex + 1) + "/" + totalBatches, ex);
            }
        });
    }
}
