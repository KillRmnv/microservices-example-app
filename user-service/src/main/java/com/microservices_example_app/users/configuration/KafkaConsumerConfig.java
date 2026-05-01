package com.microservices_example_app.users.configuration;

import com.microservices_example_app.users.event.DeleteEventEvent;
import com.microservices_example_app.users.event.MassDeleteEventMailingEvent;
import com.microservices_example_app.users.event.MassUpdateEventMailingEvent;
import com.microservices_example_app.users.event.UpdateEventEvent;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.annotation.EnableKafka;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.*;
import org.springframework.kafka.support.serializer.ErrorHandlingDeserializer;
import org.springframework.kafka.support.serializer.JacksonJsonDeserializer;
import org.springframework.kafka.support.serializer.JacksonJsonSerializer;

import java.util.HashMap;
import java.util.Map;

@EnableKafka
@Configuration
public class KafkaConsumerConfig {

    @Value("${spring.kafka.bootstrap-servers}")
    private String bootstrapServers;

    @Value("${spring.kafka.consumer.group-id}")
    private String groupId;

    private Map<String, Object> buildConsumerProps() {
        Map<String, Object> props = new HashMap<>();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ConsumerConfig.GROUP_ID_CONFIG, groupId);
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        return props;
    }

    private Map<String, Object> buildProducerProps() {
        Map<String, Object> props = new HashMap<>();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JacksonJsonSerializer.class);
        props.put(JacksonJsonSerializer.ADD_TYPE_INFO_HEADERS, false);
        return props;
    }


    @Bean
    public ConsumerFactory<String, DeleteEventEvent> deleteEventEventConsumerFactory() {
        Map<String, Object> props = buildConsumerProps();
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, ErrorHandlingDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, ErrorHandlingDeserializer.class);
        props.put(ErrorHandlingDeserializer.KEY_DESERIALIZER_CLASS, StringDeserializer.class);
        props.put(ErrorHandlingDeserializer.VALUE_DESERIALIZER_CLASS, JacksonJsonDeserializer.class);

        JacksonJsonDeserializer<DeleteEventEvent> jsonDeserializer =
                new JacksonJsonDeserializer<>(DeleteEventEvent.class, false);
        jsonDeserializer.addTrustedPackages("*");

        return new DefaultKafkaConsumerFactory<>(
                props,
                new ErrorHandlingDeserializer<>(new StringDeserializer()),
                new ErrorHandlingDeserializer<>(jsonDeserializer)
        );
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, DeleteEventEvent> deleteEventEventKafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, DeleteEventEvent> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(deleteEventEventConsumerFactory());
        return factory;
    }

    @Bean
    public ConsumerFactory<String, UpdateEventEvent> updateEventEventConsumerFactory() {
        Map<String, Object> props = buildConsumerProps();
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, ErrorHandlingDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, ErrorHandlingDeserializer.class);
        props.put(ErrorHandlingDeserializer.KEY_DESERIALIZER_CLASS, StringDeserializer.class);
        props.put(ErrorHandlingDeserializer.VALUE_DESERIALIZER_CLASS, JacksonJsonDeserializer.class);

        JacksonJsonDeserializer<UpdateEventEvent> jsonDeserializer =
                new JacksonJsonDeserializer<>(UpdateEventEvent.class, false);
        jsonDeserializer.addTrustedPackages("*");

        return new DefaultKafkaConsumerFactory<>(
                props,
                new ErrorHandlingDeserializer<>(new StringDeserializer()),
                new ErrorHandlingDeserializer<>(jsonDeserializer)
        );
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, UpdateEventEvent> updateEventEventKafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, UpdateEventEvent> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(updateEventEventConsumerFactory());
        return factory;
    }

    @Bean
    public ProducerFactory<String, MassDeleteEventMailingEvent> massDeleteProducerFactory() {
        return new DefaultKafkaProducerFactory<>(buildProducerProps());
    }

    @Bean
    public KafkaTemplate<String, MassDeleteEventMailingEvent> massDeleteKafkaTemplate() {
        return new KafkaTemplate<>(massDeleteProducerFactory());
    }

    @Bean
    public ProducerFactory<String, MassUpdateEventMailingEvent> massUpdateProducerFactory() {
        return new DefaultKafkaProducerFactory<>(buildProducerProps());
    }

    @Bean
    public KafkaTemplate<String, MassUpdateEventMailingEvent> massUpdateKafkaTemplate() {
        return new KafkaTemplate<>(massUpdateProducerFactory());
    }
}