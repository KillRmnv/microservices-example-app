package com.microservices_example_app.booking.service;

import com.microservices_example_app.booking.dto.TownCreateRequestDto;
import com.microservices_example_app.booking.dto.TownResponseDto;
import com.microservices_example_app.booking.dto.TownUpdateRequestDto;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Town;
import com.microservices_example_app.booking.producers.NotificationKafkaUserProducer;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.repository.TicketRepository;
import com.microservices_example_app.booking.repository.TownRepository;
import com.microservices_example_app.booking.repository.VenueRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Caching;
import org.springframework.stereotype.Service;

import java.util.List;
@Service
@RequiredArgsConstructor
@Slf4j
public class TownService {

    private final TownRepository townRepository;
    private final VenueRepository venueRepository;
    private final EventRepository eventRepository;
    private final TicketRepository ticketRepository;
    private final NotificationKafkaUserProducer kafkaUserProducer;

    @Value("${spring.application.name}")
    private String serviceName;

    public TownResponseDto create(TownCreateRequestDto requestDto) {
        log.info("Creating town: {}", requestDto.getName());
        Town town = Town.builder()
                .name(requestDto.getName())
                .build();
        return toResponseDto(townRepository.save(town));
    }

    public TownResponseDto getById(Integer id) {
        log.info("Fetching town with id: {}", id);
        Town town = townRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Town not found"));
        return toResponseDto(town);
    }

    public List<TownResponseDto> getAll() {
        log.info("Fetching all towns");
        return townRepository.findAll()
                .stream()
                .map(this::toResponseDto)
                .toList();
    }

    public TownResponseDto updateTownById(TownUpdateRequestDto requestDto) {
        log.info("Updating town with id: {}", requestDto.getId());
        Town town = townRepository.findById(requestDto.getId())
                .orElseThrow(() -> new NotFoundException("Town not found"));
        town.setName(requestDto.getName());
        return toResponseDto(townRepository.save(town));
    }

    @Caching(evict = {
            @CacheEvict(cacheNames = "venueSearch", allEntries = true),
            @CacheEvict(cacheNames = "venuesById", allEntries = true),
            @CacheEvict(cacheNames = "eventsById", allEntries = true),
            @CacheEvict(cacheNames = "eventSearch", allEntries = true)
    })
    @Transactional
    public void delete(Integer id) {
        // ... твой текущий код без изменений
    }

    private TownResponseDto toResponseDto(Town town) {
        return TownResponseDto.builder()
                .id(town.getId())
                .name(town.getName())
                .build();
    }
}