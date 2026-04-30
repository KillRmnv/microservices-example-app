package com.microservices_example_app.users.configuration;

import java.util.HashMap;
import java.util.Map;



import com.microservices_example_app.users.event.ForgetPasswordEvent;
import com.microservices_example_app.users.event.SuccessfulRegistrationEmailEvent;
import com.microservices_example_app.users.event.UserDeletedEvent;
import com.microservices_example_app.users.event.UserUpdatedEvent;
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
    public ProducerFactory<String, ForgetPasswordEvent>forgetPasswordProducerFactory() {
        return new DefaultKafkaProducerFactory<>(buildBaseProps());
    }

    @Bean
    public KafkaTemplate<String, ForgetPasswordEvent> forgetPasswordKafkaTemplate() {
        return new KafkaTemplate<>(forgetPasswordProducerFactory());
    }

    @Bean
    public ProducerFactory<String, SuccessfulRegistrationEmailEvent> registrationProducerFactory() {
        return new DefaultKafkaProducerFactory<>(buildBaseProps());
    }

    @Bean
    public KafkaTemplate<String, SuccessfulRegistrationEmailEvent> registrationKafkaTemplate() {
        return new KafkaTemplate<>(registrationProducerFactory());
    }

    @Bean
    public ProducerFactory<String, UserDeletedEvent> userDeletedProducerFactory() {
        return new DefaultKafkaProducerFactory<>(buildBaseProps());
    }

    @Bean
    public KafkaTemplate<String, UserDeletedEvent> userDeletedKafkaTemplate() {
        return new KafkaTemplate<>(userDeletedProducerFactory());
    }

    @Bean
    public ProducerFactory<String, UserUpdatedEvent> userUpdatedProducerFactory() {
        return new DefaultKafkaProducerFactory<>(buildBaseProps());
    }

    @Bean
    public KafkaTemplate<String, UserUpdatedEvent> userUpdatedKafkaTemplate() {
        return new KafkaTemplate<>(userUpdatedProducerFactory());
    }
}