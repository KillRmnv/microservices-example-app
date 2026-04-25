package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.EventService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/events")
@RequiredArgsConstructor
public class EventController {

    private final EventService eventService;

    @PostMapping
    public EventResponseDto create(@RequestBody EventCreateRequestDto requestDto) {
        return eventService.create(requestDto);
    }

    @GetMapping("/{id}")
    public EventResponseDto getById(@PathVariable Integer id) {
        return eventService.getById(id);
    }

    @GetMapping
    public List<EventResponseDto> getAll() {
        return eventService.getAll();
    }

    @GetMapping("/search")
    public List<EventResponseDto> searchByFilter(@ModelAttribute EventSearchRequestDto filter,
                                                 @RequestParam(defaultValue = "1") int page,
                                                 @RequestParam(defaultValue = "10") int size) {
        return eventService.searchByFilter(filter, page, size);
    }

    @PutMapping("/{id}")
    public EventResponseDto updateById(@PathVariable Integer id,
                                       @RequestBody EventUpdateRequestDto requestDto) {
        requestDto.setId(id);
        return eventService.updateEventById(requestDto);
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        eventService.deleteById(id);
    }

    @DeleteMapping("/search")
    public long deleteByFilter(@RequestBody EventDeleteRequestDto requestDto) {
        return eventService.deleteByFilter(requestDto);
    }
}