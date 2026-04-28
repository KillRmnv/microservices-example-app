package com.microservices_example_app.booking.config;

import java.util.HashMap;
import java.util.Map;


import com.microservices_example_app.booking.event.SuccessfulBookingEvent;
import com.microservices_example_app.booking.event.SuccessfulTicketRefundEvent;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.support.serializer.JacksonJsonSerializer;


@Configuration
public class KafkaProducerConfig {

    @Value("${spring.kafka.bootstrap-servers}")
    private String bootstrapServers;

    private Map<String, Object> buildBaseProps() {
        Map<String, Object> props = new HashMap<>();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JacksonJsonSerializer.class);
        return props;
    }

    @Bean
    public ProducerFactory<String, SuccessfulBookingEvent> bookingProducerFactory() {
        return new DefaultKafkaProducerFactory<>(buildBaseProps());
    }

    @Bean
    public KafkaTemplate<String, SuccessfulBookingEvent> bookingKafkaTemplate() {
        return new KafkaTemplate<>(bookingProducerFactory());
    }

    @Bean
    public ProducerFactory<String, SuccessfulTicketRefundEvent> ticketRefundProducerFactory() {
        return new DefaultKafkaProducerFactory<>(buildBaseProps());
    }

    @Bean
    public KafkaTemplate<String, SuccessfulTicketRefundEvent> ticketRefundKafkaTemplate() {
        return new KafkaTemplate<>(ticketRefundProducerFactory());
    }
}