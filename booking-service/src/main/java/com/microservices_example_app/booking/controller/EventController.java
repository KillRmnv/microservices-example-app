package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.EventService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/events")
@RequiredArgsConstructor
@Slf4j
public class EventController {

    private final EventService eventService;

    @PostMapping
    public EventResponseDto create(@Valid @RequestBody EventCreateRequestDto requestDto) {
        log.info("Creating new event: {}", requestDto.getTitle());
        return eventService.create(requestDto);
    }

    @GetMapping("/{id}")
    public EventResponseDto getById(@PathVariable Integer id) {
        log.info("Fetching event with id: {}", id);
        return eventService.getById(id);
    }

    @GetMapping
    public List<EventResponseDto> getAll() {
        log.info("Fetching all events");
        return eventService.getAll();
    }

    @GetMapping("/search")
    public List<EventResponseDto> searchByFilter(@Valid @ModelAttribute EventSearchRequestDto filter,
                                                 @RequestParam(defaultValue = "1") int page,
                                                 @RequestParam(defaultValue = "10") int size) {
        log.info("Fetching by filter page:{} , dto:{}",page,filter);
        return eventService.searchByFilter(filter, page, size);
    }

    @PutMapping("/{id}")
    public EventResponseDto updateById(@PathVariable Integer id,
                                       @Valid @RequestBody EventUpdateRequestDto requestDto) {
        log.info("Update by id:{} , dto:{}",id,requestDto);
        requestDto.setId(id);
        return eventService.updateEventById(requestDto);
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        log.info("Deleting event with id: {}", id);
        eventService.deleteById(id);
    }

    @DeleteMapping("/search")
    public long deleteByFilter(@Valid @RequestBody EventDeleteRequestDto requestDto) {
        log.info("Delete by filter:{}",requestDto);
        return eventService.deleteByFilter(requestDto);
    }
}