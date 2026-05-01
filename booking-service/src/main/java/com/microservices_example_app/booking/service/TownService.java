package com.microservices_example_app.booking.service;

import com.microservices_example_app.booking.dto.TownCreateRequestDto;
import com.microservices_example_app.booking.dto.TownResponseDto;
import com.microservices_example_app.booking.dto.TownUpdateRequestDto;
import com.microservices_example_app.booking.event.DeleteEventEvent;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.Ticket;
import com.microservices_example_app.booking.model.Town;
import com.microservices_example_app.booking.model.Venue;
import com.microservices_example_app.booking.producers.NotificationKafkaUserProducer;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.repository.TicketRepository;
import com.microservices_example_app.booking.repository.TownRepository;
import com.microservices_example_app.booking.repository.VenueRepository;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
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
    @PersistenceContext
    private EntityManager entityManager;
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
        log.info("Deleting town with id: {}", id);

        townRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Town not found"));

        List<Integer> venueIds = venueRepository.findByTownId(id)
                .stream().map(Venue::getId).toList();

        List<String> eventTitles = List.of();
        List<Integer> userIds = List.of();

        if (!venueIds.isEmpty()) {
            List<Event> events = eventRepository.findByVenueIdIn(venueIds);

            if (!events.isEmpty()) {
                List<Integer> eventIds = events.stream().map(Event::getId).toList();
                eventTitles = events.stream().map(Event::getTitle).toList();
                userIds = ticketRepository.findByEventIdInAndUserIdIsNotNull(eventIds)
                        .stream()
                        .map(Ticket::getUserId)
                        .distinct()
                        .toList();
            }
        }

        entityManager.clear();

        townRepository.deleteById(id);
        townRepository.flush();

        if (!eventTitles.isEmpty()) {
            kafkaUserProducer.sendDeleteEventEvent(new DeleteEventEvent(
                    eventTitles, serviceName, userIds
            ));
            log.info("DeleteEventEvent sent: {} events, {} users affected",
                    eventTitles.size(), userIds.size());
        }
    }
    private TownResponseDto toResponseDto(Town town) {
        return TownResponseDto.builder()
                .id(town.getId())
                .name(town.getName())
                .build();
    }
}