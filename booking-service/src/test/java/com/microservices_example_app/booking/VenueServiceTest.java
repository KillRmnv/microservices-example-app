package com.microservices_example_app.booking;

import com.microservices_example_app.booking.dto.VenueCreateRequestDto;
import com.microservices_example_app.booking.dto.VenueDeleteRequestDto;
import com.microservices_example_app.booking.dto.VenueResponseDto;
import com.microservices_example_app.booking.dto.VenueSearchRequestDto;
import com.microservices_example_app.booking.dto.VenueUpdateRequestDto;
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
import com.microservices_example_app.booking.service.VenueService;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(org.mockito.junit.jupiter.MockitoExtension.class)
class VenueServiceTest {

    @Mock
    private VenueRepository venueRepository;

    @Mock
    private TownRepository townRepository;

    @Mock
    private EventRepository eventRepository;

    @Mock
    private TicketRepository ticketRepository;

    @Mock
    private NotificationKafkaUserProducer kafkaUserProducer;

    @Mock
    private EntityManager entityManager;

    @InjectMocks
    private VenueService venueService;

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(venueService, "entityManager", entityManager);
        ReflectionTestUtils.setField(venueService, "serviceName", "booking-service");
    }

    @Test
    void create_shouldCreateVenue() {
        VenueCreateRequestDto request = new VenueCreateRequestDto();
        request.setTownId(10);
        request.setPlace("Main Hall");
        request.setCapacity(5000);

        Town town = Town.builder()
                .id(10)
                .name("Berlin")
                .build();

        Venue savedVenue = Venue.builder()
                .id(100)
                .town(town)
                .place("Main Hall")
                .capacity(5000)
                .build();

        when(townRepository.findById(10)).thenReturn(Optional.of(town));
        when(venueRepository.save(any(Venue.class))).thenReturn(savedVenue);

        VenueResponseDto result = venueService.create(request);

        assertThat(result).isNotNull();
        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getTownId()).isEqualTo(10);
        assertThat(result.getTownName()).isEqualTo("Berlin");
        assertThat(result.getPlace()).isEqualTo("Main Hall");
        assertThat(result.getCapacity()).isEqualTo(5000);

        ArgumentCaptor<Venue> captor = ArgumentCaptor.forClass(Venue.class);
        verify(venueRepository).save(captor.capture());

        Venue actual = captor.getValue();
        assertThat(actual.getTown().getId()).isEqualTo(10);
        assertThat(actual.getPlace()).isEqualTo("Main Hall");
        assertThat(actual.getCapacity()).isEqualTo(5000);
    }

    @Test
    void create_shouldThrowWhenTownNotFound() {
        VenueCreateRequestDto request = new VenueCreateRequestDto();
        request.setTownId(10);

        when(townRepository.findById(10)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> venueService.create(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Town not found");

        verify(venueRepository, never()).save(any());
    }

    @Test
    void getById_shouldReturnVenue() {
        Town town = Town.builder()
                .id(10)
                .name("Berlin")
                .build();

        Venue venue = Venue.builder()
                .id(100)
                .town(town)
                .place("Main Hall")
                .capacity(5000)
                .build();

        when(venueRepository.findById(100)).thenReturn(Optional.of(venue));

        VenueResponseDto result = venueService.getById(100);

        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getTownId()).isEqualTo(10);
        assertThat(result.getTownName()).isEqualTo("Berlin");
        assertThat(result.getPlace()).isEqualTo("Main Hall");
        assertThat(result.getCapacity()).isEqualTo(5000);
    }

    @Test
    void getById_shouldThrowWhenVenueNotFound() {
        when(venueRepository.findById(100)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> venueService.getById(100))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Venue not found");
    }

    @Test
    void deleteById_shouldDeleteVenue() {
        Venue venue = Venue.builder()
                .id(100)
                .place("Main Hall")
                .build();

        when(venueRepository.findById(100)).thenReturn(Optional.of(venue));
        when(eventRepository.findByVenueId(100)).thenReturn(List.of());

        venueService.deleteById(100);

        verify(venueRepository).findById(100);
        verify(venueRepository).deleteById(100);
        verify(venueRepository).flush();
    }

    @Test
    void deleteById_shouldThrowWhenIdInvalid() {
        assertThatThrownBy(() -> venueService.deleteById(0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Venue id must be positive");

        verify(venueRepository, never()).findById(anyInt());
        verify(venueRepository, never()).deleteById(anyInt());
    }

    @Test
    void deleteById_shouldThrowWhenVenueNotFound() {
        when(venueRepository.findById(100)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> venueService.deleteById(100))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Venue not found");

        verify(venueRepository).findById(100);
        verify(venueRepository, never()).deleteById(anyInt());
    }

    @Test
    void deleteByFilter_shouldDeleteMatchedVenuesAndReturnCount() {
        VenueDeleteRequestDto request = new VenueDeleteRequestDto();
        request.setTownId(10);
        request.setPlace("Main Hall");
        request.setMinCapacity(1000);
        request.setMaxCapacity(10000);

        Town town = Town.builder()
                .id(10)
                .name("Berlin")
                .build();

        Venue venue1 = Venue.builder()
                .id(100)
                .town(town)
                .place("Main Hall")
                .capacity(5000)
                .build();

        Venue venue2 = Venue.builder()
                .id(101)
                .town(town)
                .place("Main Hall")
                .capacity(7000)
                .build();

        when(venueRepository.findAll(any(Specification.class)))
                .thenReturn(List.of(venue1, venue2));
        when(eventRepository.findByVenueIdIn(anyList())).thenReturn(List.of());

        long result = venueService.deleteByFilter(request);

        assertThat(result).isEqualTo(2);
        verify(venueRepository).findAll(any(Specification.class));
        verify(venueRepository).deleteAll(List.of(venue1, venue2));
    }

    @Test
    void searchByFilter_shouldReturnVenues() {
        VenueSearchRequestDto filter = new VenueSearchRequestDto();
        filter.setTownId(10);
        filter.setPlace("Main Hall");
        filter.setMinCapacity(1000);
        filter.setMaxCapacity(10000);

        Town town = Town.builder()
                .id(10)
                .name("Berlin")
                .build();

        Venue venue = Venue.builder()
                .id(100)
                .town(town)
                .place("Main Hall")
                .capacity(5000)
                .build();

        when(venueRepository.findAll(any(Specification.class), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(venue)));

        List<VenueResponseDto> result = venueService.searchByFilter(filter, 1, 10);

        assertThat(result).hasSize(1);
        assertThat(result.getFirst().getId()).isEqualTo(100);
        assertThat(result.getFirst().getTownName()).isEqualTo("Berlin");
        assertThat(result.getFirst().getPlace()).isEqualTo("Main Hall");
        assertThat(result.getFirst().getCapacity()).isEqualTo(5000);

        verify(venueRepository).findAll(any(Specification.class), any(Pageable.class));
    }

    @Test
    void searchByFilter_shouldThrowWhenPageLessThanOne() {
        VenueSearchRequestDto filter = new VenueSearchRequestDto();

        assertThatThrownBy(() -> venueService.searchByFilter(filter, 0, 10))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Page must be >= 1");
    }

    @Test
    void searchByFilter_shouldThrowWhenSizeLessThanOne() {
        VenueSearchRequestDto filter = new VenueSearchRequestDto();

        assertThatThrownBy(() -> venueService.searchByFilter(filter, 1, 0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Size must be >= 1");
    }

    @Test
    void updateVenueById_shouldUpdateVenue() {
        VenueUpdateRequestDto request = new VenueUpdateRequestDto();
        request.setId(100);
        request.setTownId(11);
        request.setPlace("New Hall");
        request.setCapacity(8000);

        Town oldTown = Town.builder()
                .id(10)
                .name("Berlin")
                .build();

        Town newTown = Town.builder()
                .id(11)
                .name("Munich")
                .build();

        Venue existing = Venue.builder()
                .id(100)
                .town(oldTown)
                .place("Old Hall")
                .capacity(5000)
                .build();

        Venue updated = Venue.builder()
                .id(100)
                .town(newTown)
                .place("New Hall")
                .capacity(8000)
                .build();

        when(venueRepository.findById(100)).thenReturn(Optional.of(existing));
        when(townRepository.findById(11)).thenReturn(Optional.of(newTown));
        when(venueRepository.save(any(Venue.class))).thenReturn(updated);
        when(eventRepository.findByVenueId(100)).thenReturn(List.of());

        VenueResponseDto result = venueService.updateVenueById(request);

        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getTownId()).isEqualTo(11);
        assertThat(result.getTownName()).isEqualTo("Munich");
        assertThat(result.getPlace()).isEqualTo("New Hall");
        assertThat(result.getCapacity()).isEqualTo(8000);

        ArgumentCaptor<Venue> captor = ArgumentCaptor.forClass(Venue.class);
        verify(venueRepository).save(captor.capture());

        Venue actual = captor.getValue();
        assertThat(actual.getId()).isEqualTo(100);
        assertThat(actual.getTown().getId()).isEqualTo(11);
        assertThat(actual.getPlace()).isEqualTo("New Hall");
        assertThat(actual.getCapacity()).isEqualTo(8000);
    }

    @Test
    void updateVenueById_shouldThrowWhenVenueNotFound() {
        VenueUpdateRequestDto request = new VenueUpdateRequestDto();
        request.setId(100);

        when(venueRepository.findById(100)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> venueService.updateVenueById(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("No venue with id=100");

        verify(venueRepository, never()).save(any());
    }

    @Test
    void updateVenueById_shouldThrowWhenTownNotFound() {
        VenueUpdateRequestDto request = new VenueUpdateRequestDto();
        request.setId(100);
        request.setTownId(11);

        Town oldTown = Town.builder()
                .id(10)
                .name("Berlin")
                .build();

        Venue existing = Venue.builder()
                .id(100)
                .town(oldTown)
                .place("Old Hall")
                .capacity(5000)
                .build();

        when(venueRepository.findById(100)).thenReturn(Optional.of(existing));
        when(townRepository.findById(11)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> venueService.updateVenueById(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Town not found: 11");

        verify(venueRepository, never()).save(any());
    }

    @Test
    void getAll_shouldReturnAllVenues() {
        Town town = Town.builder().id(10).name("Berlin").build();
        Venue venue = Venue.builder().id(100).town(town).place("Main Hall").capacity(5000).build();
        when(venueRepository.findAll()).thenReturn(List.of(venue));
        List<VenueResponseDto> result = venueService.getAll();
        assertThat(result).hasSize(1);
        assertThat(result.getFirst().getPlace()).isEqualTo("Main Hall");
    }

    @Test
    void getAll_shouldReturnEmptyList() {
        when(venueRepository.findAll()).thenReturn(List.of());
        List<VenueResponseDto> result = venueService.getAll();
        assertThat(result).isEmpty();
    }

    @Test
    void updateVenueById_shouldThrowWhenIdNegative() {
        VenueUpdateRequestDto request = new VenueUpdateRequestDto();
        request.setId(-1);
        assertThatThrownBy(() -> venueService.updateVenueById(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Venue id must be positive");
    }

    @Test
    void deleteById_shouldDeleteVenueWithEventsAndSendKafka() {
        Venue venue = Venue.builder().id(100).place("Main Hall").build();
        Event event = Event.builder().id(10).title("Concert").venue(venue).build();
        when(venueRepository.findById(100)).thenReturn(Optional.of(venue));
        when(eventRepository.findByVenueId(100)).thenReturn(List.of(event));
        when(ticketRepository.findByEventIdIn(List.of(10))).thenReturn(List.of());
        venueService.deleteById(100);
        verify(venueRepository).deleteById(100);
        verify(kafkaUserProducer).sendDeleteEventEvent(any());
    }


    @Test
    void updateVenueById_shouldDeactivateExcessTicketsWhenCapacityReduced() {
        VenueUpdateRequestDto request = new VenueUpdateRequestDto();
        request.setId(100);
        request.setCapacity(1);
        Town town = Town.builder().id(10).name("Berlin").build();
        Venue existing = Venue.builder().id(100).town(town).place("Main Hall").capacity(5).build();
        Venue saved = Venue.builder().id(100).town(town).place("Main Hall").capacity(1).build();
        Event event = Event.builder().id(10).title("Concert").venue(existing).build();
        Ticket ticket1 = Ticket.builder().id(1).event(event).userId(77).active(true).build();
        Ticket ticket2 = Ticket.builder().id(2).event(event).userId(88).active(true).build();
        Ticket ticket3 = Ticket.builder().id(3).event(event).userId(99).active(true).build();
        when(venueRepository.findById(100)).thenReturn(Optional.of(existing));
        when(venueRepository.save(any(Venue.class))).thenReturn(saved);
        when(eventRepository.findByVenueId(100)).thenReturn(List.of(event));
        when(ticketRepository.findByEventIdIn(List.of(10))).thenReturn(List.of(ticket1, ticket2, ticket3));
        when(ticketRepository.findByEventIdInAndUserIdIsNotNullOrderByIdDesc(List.of(10))).thenReturn(List.of(ticket3, ticket2, ticket1));
        VenueResponseDto result = venueService.updateVenueById(request);
        assertThat(result.getCapacity()).isEqualTo(1);
        verify(ticketRepository).saveAll(argThat(tickets -> {
            java.util.List<?> list = (java.util.List<?>) tickets;
            return list.size() == 2;
        }));
        verify(kafkaUserProducer).sendDeleteEventEvent(any());
    }

    @Test
    void updateVenueById_shouldNotDeactivateWhenNoExcess() {
        VenueUpdateRequestDto request = new VenueUpdateRequestDto();
        request.setId(100);
        request.setCapacity(3);
        Town town = Town.builder().id(10).name("Berlin").build();
        Venue existing = Venue.builder().id(100).town(town).place("Main Hall").capacity(5).build();
        Venue saved = Venue.builder().id(100).town(town).place("Main Hall").capacity(3).build();
        Event event = Event.builder().id(10).title("Concert").venue(existing).build();
        Ticket ticket1 = Ticket.builder().id(1).event(event).userId(77).active(true).build();
        when(venueRepository.findById(100)).thenReturn(Optional.of(existing));
        when(venueRepository.save(any(Venue.class))).thenReturn(saved);
        when(eventRepository.findByVenueId(100)).thenReturn(List.of(event));
        when(ticketRepository.findByEventIdIn(List.of(10))).thenReturn(List.of(ticket1));
        when(ticketRepository.findByEventIdInAndUserIdIsNotNullOrderByIdDesc(List.of(10))).thenReturn(List.of(ticket1));
        VenueResponseDto result = venueService.updateVenueById(request);
        assertThat(result.getCapacity()).isEqualTo(3);
        verify(ticketRepository, never()).saveAll(any());
    }


    @Test
    void deleteByFilter_shouldIncludeUserIdsWhenVenuesHaveEvents() {
        VenueDeleteRequestDto request = new VenueDeleteRequestDto();
        request.setTownId(10);
        Town town = Town.builder().id(10).name("Berlin").build();
        Venue venue = Venue.builder().id(100).town(town).place("Main Hall").capacity(5000).build();
        Event event = Event.builder().id(10).title("Concert").venue(venue).build();
        Ticket ticket = Ticket.builder().id(1).event(event).userId(77).build();
        when(venueRepository.findAll(any(Specification.class))).thenReturn(List.of(venue));
        when(eventRepository.findByVenueIdIn(List.of(100))).thenReturn(List.of(event));
        when(ticketRepository.findByEventIdIn(List.of(10))).thenReturn(List.of(ticket));
        long result = venueService.deleteByFilter(request);
        assertThat(result).isEqualTo(1);
        verify(kafkaUserProducer).sendDeleteEventEvent(argThat(e ->
                e.getUserIds().contains(77)
        ));
    }

    @Test
    void deleteByFilter_shouldReturnZeroWhenNoMatch() {
        VenueDeleteRequestDto request = new VenueDeleteRequestDto();
        request.setPlace("Nonexistent");
        when(venueRepository.findAll(any(Specification.class))).thenReturn(List.of());
        long result = venueService.deleteByFilter(request);
        assertThat(result).isEqualTo(0);
    }


    @Test
    void updateVenueById_shouldKeepFieldsWhenNull() {
        VenueUpdateRequestDto request = new VenueUpdateRequestDto();
        request.setId(100);
        Town town = Town.builder().id(10).name("Berlin").build();
        Venue existing = Venue.builder().id(100).town(town).place("Main Hall").capacity(5000).build();
        Venue saved = Venue.builder().id(100).town(town).place("Main Hall").capacity(5000).build();
        when(venueRepository.findById(100)).thenReturn(Optional.of(existing));
        when(venueRepository.save(any(Venue.class))).thenReturn(saved);
        when(eventRepository.findByVenueId(100)).thenReturn(List.of());
        VenueResponseDto result = venueService.updateVenueById(request);
        assertThat(result.getPlace()).isEqualTo("Main Hall");
        assertThat(result.getCapacity()).isEqualTo(5000);
        assertThat(result.getTownId()).isEqualTo(10);
    }
}