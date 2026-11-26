package com.microservices_example_app.booking.config;

import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.common.config.TopicConfig;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.TopicBuilder;

/**
 * Catalog stream topic. Compacted and never expired, because the collector
 * rebuilds its search index by replaying it from offset zero.
 */
@Configuration
public class KafkaTopicConfig {

    @Bean
    public NewTopic bookingCatalogTopic(
            @Value("${topic.booking.catalog:booking.catalog}") String topic) {
        return TopicBuilder.name(topic)
                .partitions(1)
                .replicas(1)
                .config(TopicConfig.CLEANUP_POLICY_CONFIG,
                        TopicConfig.CLEANUP_POLICY_COMPACT)
                .config(TopicConfig.RETENTION_MS_CONFIG, "-1")
                .build();
    }
}
