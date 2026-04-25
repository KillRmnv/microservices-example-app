package com.microservices_example_app.booking.config;

import org.springframework.boot.cache.autoconfigure.RedisCacheManagerBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.serializer.GenericJacksonJsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;
import tools.jackson.databind.ObjectMapper;

import java.time.Duration;

@Configuration
public class RedisConfig {

    @Bean
    public RedisCacheManagerBuilderCustomizer redisCacheManagerBuilderCustomizer() {
        GenericJacksonJsonRedisSerializer serializer =
                new GenericJacksonJsonRedisSerializer(new ObjectMapper());

        return builder -> builder
                .withCacheConfiguration(
                        "eventsById",
                        RedisCacheConfiguration.defaultCacheConfig()
                                .entryTtl(Duration.ofMinutes(10))
                                .disableCachingNullValues()
                                .serializeValuesWith(
                                        RedisSerializationContext.SerializationPair.fromSerializer(serializer)
                                )
                )
                .withCacheConfiguration(
                        "eventSearch",
                        RedisCacheConfiguration.defaultCacheConfig()
                                .entryTtl(Duration.ofMinutes(5))
                                .disableCachingNullValues()
                                .serializeValuesWith(
                                        RedisSerializationContext.SerializationPair.fromSerializer(serializer)
                                )
                )
                .withCacheConfiguration(
                        "venueSearch",
                        RedisCacheConfiguration.defaultCacheConfig()
                                .entryTtl(Duration.ofMinutes(5))
                                .disableCachingNullValues()
                                .serializeValuesWith(
                                        RedisSerializationContext.SerializationPair.fromSerializer(serializer)
                                )
                ).withCacheConfiguration(
                        "venuesById",
                        RedisCacheConfiguration.defaultCacheConfig()
                                .entryTtl(Duration.ofMinutes(10))
                                .disableCachingNullValues()
                                .serializeValuesWith(
                                        RedisSerializationContext.SerializationPair.fromSerializer(serializer)
                                )
                );
    }
}