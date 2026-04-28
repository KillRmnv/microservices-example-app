package com.microservices_example_app.notification.config;

import com.microservices_example_app.notification.dto.ForgetPasswordEvent;
import com.microservices_example_app.notification.dto.SuccessfulBookingEvent;

import com.microservices_example_app.notification.dto.SuccessfulRegistrationEmailEvent;
import com.microservices_example_app.notification.dto.TicketRefundEvent;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.annotation.EnableKafka;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.support.serializer.ErrorHandlingDeserializer;
import org.springframework.kafka.support.serializer.JacksonJsonDeserializer;

import java.util.HashMap;
import java.util.Map;

@EnableKafka
@Configuration
public class KafkaConsumerConfig {

    @Value("${spring.kafka.bootstrap-servers}")
    private String bootstrapServers;

    @Value("${spring.kafka.consumer.group-id}")
    private String groupId;

    private Map<String, Object> buildBaseProps() {
        Map<String, Object> props = new HashMap<>();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ConsumerConfig.GROUP_ID_CONFIG, groupId);
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        return props;
    }

    @Bean
    public ConsumerFactory<String, SuccessfulBookingEvent> bookingConsumerFactory() {
        JacksonJsonDeserializer<SuccessfulBookingEvent> deserializer =
                new JacksonJsonDeserializer<>(SuccessfulBookingEvent.class, false);
        deserializer.addTrustedPackages("com.microservices_example_app.notification.dto");

        Map<String, Object> props = buildBaseProps();
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, JacksonJsonDeserializer.class);

        return new DefaultKafkaConsumerFactory<>(props, new StringDeserializer(), deserializer);
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, SuccessfulBookingEvent> bookingKafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, SuccessfulBookingEvent> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(bookingConsumerFactory());
        return factory;
    }

    @Bean
    public ConsumerFactory<String, SuccessfulRegistrationEmailEvent> successfulRegistrationConsumerFactory() {
        Map<String, Object> props = buildBaseProps();
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, ErrorHandlingDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, ErrorHandlingDeserializer.class);
        props.put(ErrorHandlingDeserializer.KEY_DESERIALIZER_CLASS, StringDeserializer.class);
        props.put(ErrorHandlingDeserializer.VALUE_DESERIALIZER_CLASS, JacksonJsonDeserializer.class);

        JacksonJsonDeserializer<SuccessfulRegistrationEmailEvent> jsonDeserializer =
                new JacksonJsonDeserializer<>(SuccessfulRegistrationEmailEvent.class, false);
        jsonDeserializer.addTrustedPackages("com.microservices_example_app.notification.dto");

        return new DefaultKafkaConsumerFactory<>(
                props,
                new ErrorHandlingDeserializer<>(new StringDeserializer()),
                new ErrorHandlingDeserializer<>(jsonDeserializer)
        );
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, SuccessfulRegistrationEmailEvent> successfulRegistrationKafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, SuccessfulRegistrationEmailEvent> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(successfulRegistrationConsumerFactory());
        return factory;
    }

    @Bean
    public ConsumerFactory<String, ForgetPasswordEvent> forgetPasswordConsumerFactory() {
        Map<String, Object> props = buildBaseProps();
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, ErrorHandlingDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, ErrorHandlingDeserializer.class);
        props.put(ErrorHandlingDeserializer.KEY_DESERIALIZER_CLASS, StringDeserializer.class);
        props.put(ErrorHandlingDeserializer.VALUE_DESERIALIZER_CLASS, JacksonJsonDeserializer.class);

        JacksonJsonDeserializer<ForgetPasswordEvent> jsonDeserializer =
                new JacksonJsonDeserializer<>(ForgetPasswordEvent.class, false);
        jsonDeserializer.addTrustedPackages("com.microservices_example_app.notification.dto");

        return new DefaultKafkaConsumerFactory<>(
                props,
                new ErrorHandlingDeserializer<>(new StringDeserializer()),
                new ErrorHandlingDeserializer<>(jsonDeserializer)
        );
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, ForgetPasswordEvent> forgetPasswordKafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, ForgetPasswordEvent> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(forgetPasswordConsumerFactory());
        return factory;
    }
    @Bean
    public ConsumerFactory<String, TicketRefundEvent> ticketRefundConsumerFactory() {
        JacksonJsonDeserializer<TicketRefundEvent> deserializer =
                new JacksonJsonDeserializer<>(TicketRefundEvent.class, false);
        deserializer.addTrustedPackages("com.microservices_example_app.notification.dto");

        Map<String, Object> props = buildBaseProps();
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, ErrorHandlingDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, ErrorHandlingDeserializer.class);
        props.put(ErrorHandlingDeserializer.KEY_DESERIALIZER_CLASS, StringDeserializer.class);
        props.put(ErrorHandlingDeserializer.VALUE_DESERIALIZER_CLASS, JacksonJsonDeserializer.class);

        return new DefaultKafkaConsumerFactory<>(
                props,
                new ErrorHandlingDeserializer<>(new StringDeserializer()),
                new ErrorHandlingDeserializer<>(deserializer)
        );
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, TicketRefundEvent> ticketRefundKafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, TicketRefundEvent> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(ticketRefundConsumerFactory());
        return factory;
    }
}