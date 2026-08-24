package com.microservices_example_app.users.utils;

import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@Component
@Slf4j
public class TransactionalEventPublisher {

    public <K, V> void sendAfterCommit(KafkaTemplate<K, V> template, String topic, K key, V payload) {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            log.warn("No active transaction — sending Kafka event immediately for topic={}", topic);
            template.send(topic, key, payload);
            return;
        }
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                template.send(topic, key, payload)
                        .whenComplete((result, ex) -> {
                            if (ex != null) {
                                log.error("Failed to send Kafka event to topic={}: {}", topic, ex.getMessage(), ex);
                            } else {
                                log.info("Kafka event sent to topic={} after commit", topic);
                            }
                        });
            }
        });
    }
}
