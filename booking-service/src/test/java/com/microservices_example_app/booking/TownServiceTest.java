package com.microservices_example_app.booking;

import com.microservices_example_app.booking.dto.TownCreateRequestDto;
import com.microservices_example_app.booking.dto.TownResponseDto;
import com.microservices_example_app.booking.dto.TownUpdateRequestDto;
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
import com.microservices_example_app.booking.service.TownService;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(org.mockito.junit.jupiter.MockitoExtension.class)
class TownServiceTest {

    @Mock
    private TownRepository townRepository;

    @Mock
    private VenueRepository venueRepository;

    @Mock
    private EventRepository eventRepository;

    @Mock
    private TicketRepository ticketRepository;

    @Mock
    private NotificationKafkaUserProducer kafkaUserProducer;

    @Mock
    private EntityManager entityManager;

    @InjectMocks
    private TownService townService;

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(townService, "entityManager", entityManager);
        ReflectionTestUtils.setField(townService, "serviceName", "booking-service");
    }

    @Test
    void create_shouldCreateTown() {
        TownCreateRequestDto request = new TownCreateRequestDto();
        request.setName("Berlin");
        Town saved = Town.builder().id(1).name("Berlin").build();
        when(townRepository.save(any(Town.class))).thenReturn(saved);
        TownResponseDto result = townService.create(request);
        assertThat(result).isNotNull();
        assertThat(result.getId()).isEqualTo(1);
        assertThat(result.getName()).isEqualTo("Berlin");
    }

    @Test
    void getById_shouldReturnTown() {
        Town town = Town.builder().id(1).name("Berlin").build();
        when(townRepository.findById(1)).thenReturn(Optional.of(town));
        TownResponseDto result = townService.getById(1);
        assertThat(result.getId()).isEqualTo(1);
        assertThat(result.getName()).isEqualTo("Berlin");
    }

    @Test
    void getById_shouldThrowWhenTownNotFound() {
        when(townRepository.findById(1)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> townService.getById(1))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Town not found");
    }

    @Test
    void getAll_shouldReturnAllTowns() {
        Town town1 = Town.builder().id(1).name("Berlin").build();
        Town town2 = Town.builder().id(2).name("Munich").build();
        when(townRepository.findAll()).thenReturn(List.of(town1, town2));
        List<TownResponseDto> result = townService.getAll();
        assertThat(result).hasSize(2);
        assertThat(result.getFirst().getName()).isEqualTo("Berlin");
    }

    @Test
    void getAll_shouldReturnEmptyList() {
        when(townRepository.findAll()).thenReturn(List.of());
        List<TownResponseDto> result = townService.getAll();
        assertThat(result).isEmpty();
    }

    @Test
    void updateTownById_shouldUpdateTown() {
        TownUpdateRequestDto request = new TownUpdateRequestDto();
        request.setId(1);
        request.setName("Munich");
        Town existing = Town.builder().id(1).name("Berlin").build();
        Town saved = Town.builder().id(1).name("Munich").build();
        when(townRepository.findById(1)).thenReturn(Optional.of(existing));
        when(townRepository.save(any(Town.class))).thenReturn(saved);
        TownResponseDto result = townService.updateTownById(request);
        assertThat(result.getName()).isEqualTo("Munich");
    }

    @Test
    void updateTownById_shouldThrowWhenTownNotFound() {
        TownUpdateRequestDto request = new TownUpdateRequestDto();
        request.setId(1);
        request.setName("Munich");
        when(townRepository.findById(1)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> townService.updateTownById(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Town not found");
    }

    @Test
    void delete_shouldDeleteTown() {
        Town town = Town.builder().id(1).name("Berlin").build();
        when(townRepository.findById(1)).thenReturn(Optional.of(town));
        when(venueRepository.findByTownId(1)).thenReturn(List.of());
        townService.delete(1);
        verify(townRepository).deleteById(1);
        verify(townRepository).flush();
    }

    @Test
    void delete_shouldThrowWhenTownNotFound() {
        when(townRepository.findById(1)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> townService.delete(1))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Town not found");
    }

    @Test
    void delete_shouldSendKafkaWhenVenuesHaveEvents() {
        Town town = Town.builder().id(1).name("Berlin").build();
        Venue venue = Venue.builder().id(10).town(town).place("Hall").build();
        Event event = Event.builder().id(100).title("Concert").venue(venue).build();
        when(townRepository.findById(1)).thenReturn(Optional.of(town));
        when(venueRepository.findByTownId(1)).thenReturn(List.of(venue));
        when(eventRepository.findByVenueIdIn(List.of(10))).thenReturn(List.of(event));
        when(ticketRepository.findByEventIdInAndUserIdIsNotNull(List.of(100))).thenReturn(List.of());
        townService.delete(1);
        verify(kafkaUserProducer).sendDeleteEventEvent(any());
    }

    @Test
    void delete_shouldNotSendKafkaWhenNoEvents() {
        Town town = Town.builder().id(1).name("Berlin").build();
        Venue venue = Venue.builder().id(10).town(town).place("Hall").build();
        when(townRepository.findById(1)).thenReturn(Optional.of(town));
        when(venueRepository.findByTownId(1)).thenReturn(List.of(venue));
        when(eventRepository.findByVenueIdIn(List.of(10))).thenReturn(List.of());
        townService.delete(1);
        verify(kafkaUserProducer, never()).sendDeleteEventEvent(any());
    }

    // ==================== edge cases ====================

    @Test
    void updateTownById_shouldSetNullNameWhenProvided() {
        TownUpdateRequestDto request = new TownUpdateRequestDto();
        request.setId(1);
        request.setName(null);
        Town existing = Town.builder().id(1).name("Berlin").build();
        Town saved = Town.builder().id(1).name(null).build();
        when(townRepository.findById(1)).thenReturn(Optional.of(existing));
        when(townRepository.save(any(Town.class))).thenReturn(saved);
        TownResponseDto result = townService.updateTownById(request);
        assertThat(result.getName()).isNull();
    }

    @Test
    void delete_shouldDeleteTownWithVenuesButNoEvents() {
        Town town = Town.builder().id(1).name("Berlin").build();
        Venue venue = Venue.builder().id(10).town(town).place("Hall").build();
        when(townRepository.findById(1)).thenReturn(Optional.of(town));
        when(venueRepository.findByTownId(1)).thenReturn(List.of(venue));
        when(eventRepository.findByVenueIdIn(List.of(10))).thenReturn(List.of());
        townService.delete(1);
        verify(townRepository).deleteById(1);
        verify(kafkaUserProducer, never()).sendDeleteEventEvent(any());
    }

    @Test
    void delete_shouldCollectUserIdsWhenTicketsExist() {
        Town town = Town.builder().id(1).name("Berlin").build();
        Venue venue = Venue.builder().id(10).town(town).place("Hall").build();
        Event event = Event.builder().id(100).title("Concert").venue(venue).build();
        Ticket ticket1 = Ticket.builder().id(1).event(event).userId(77).build();
        Ticket ticket2 = Ticket.builder().id(2).event(event).userId(88).build();
        when(townRepository.findById(1)).thenReturn(Optional.of(town));
        when(venueRepository.findByTownId(1)).thenReturn(List.of(venue));
        when(eventRepository.findByVenueIdIn(List.of(10))).thenReturn(List.of(event));
        when(ticketRepository.findByEventIdInAndUserIdIsNotNull(List.of(100))).thenReturn(List.of(ticket1, ticket2));
        townService.delete(1);
        verify(kafkaUserProducer).sendDeleteEventEvent(argThat(e ->
                e.getUserIds().contains(77) && e.getUserIds().contains(88)
        ));
    }
}
