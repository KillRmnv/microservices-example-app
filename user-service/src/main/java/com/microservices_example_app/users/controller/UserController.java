package com.microservices_example_app.users.controller;

import com.microservices_example_app.users.dto.*;
import com.microservices_example_app.users.service.UserService;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Slf4j
@RestController
@RequestMapping("/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping
    public ResponseEntity<List<UserResponseDto>> getAll() {
        log.info("Request received: get all users");
        List<UserResponseDto> users = userService.getAll();
        log.info("Successfully returned {} users", users.size());
        return ResponseEntity.ok(users);
    }

    @GetMapping("/{id}")
    public ResponseEntity<UserResponseDto> getById(@PathVariable int id) {
        log.info("Request received: get user by id={}", id);
        UserResponseDto user = userService.getById(id);
        log.info("Successfully returned user with id={}", id);
        return ResponseEntity.ok(user);
    }

    @GetMapping("/by-email")
    public ResponseEntity<UserResponseDto> getByEmail(@RequestParam String email) {
        log.info("Request received: get user by email={}", email);
        UserResponseDto user = userService.getByEmail(email);
        log.info("Successfully returned user by email={}", email);
        return ResponseEntity.ok(user);
    }

    @GetMapping("/page")
    public ResponseEntity<List<UserResponseDto>> getUsersByPage(
            @RequestParam int page,
            @RequestParam int size
    ) {
        log.info("Request received: get users by page, page={}, size={}", page, size);
        List<UserResponseDto> users = userService.getUsersByPage(page, size);
        log.info("Successfully returned {} users for page={}, size={}", users.size(), page, size);
        return ResponseEntity.ok(users);
    }

    @GetMapping("/search")
    public ResponseEntity<List<UserResponseDto>> searchByFilter(@Valid @ModelAttribute UserSerchRequestDto filter) {
        log.info("Request received: search users by filter, email={}, username={}, role={}",
                filter.getEmail(), filter.getUsername(), filter.getRole());
        List<UserResponseDto> users = userService.searchByFilter(filter);
        log.info("Search completed: found {} users", users.size());
        return ResponseEntity.ok(users);
    }

    @GetMapping("/search/page")
    public ResponseEntity<List<UserResponseDto>> searchByFilterWithPage(
            @Valid @ModelAttribute UserSerchRequestDto filter,
            @RequestParam int page,
            @RequestParam int size
    ) {
        log.info("Request received: search users by filter with paging, email={}, username={}, role={}, page={}, size={}",
                filter.getEmail(), filter.getUsername(), filter.getRole(), page, size);
        List<UserResponseDto> users = userService.searchByFilter(filter, page, size);
        log.info("Paged search completed: found {} users for page={}, size={}", users.size(), page, size);
        return ResponseEntity.ok(users);
    }

    @PutMapping
    public ResponseEntity<UserResponseDto> updateUser(@Valid @RequestBody UserUpdateRequestDto request) {
        log.info("Request received: update user id={}", request.getId());
        UserResponseDto updated = userService.updateUserById(request);
        log.info("User updated successfully: id={}", request.getId());
        return ResponseEntity.ok(updated);
    }

    @DeleteMapping
    public ResponseEntity<Void> deleteUser(@Valid @RequestBody UserDeleteRequestDto request) {
        log.info("Request received: delete user id={}", request.getId());
        userService.deleteUser(request);
        log.info("User deleted successfully: id={}", request.getId());
        return ResponseEntity.noContent().build();
    }

    @DeleteMapping("/search")
    public ResponseEntity<Long> deleteByFilter(@Valid @RequestBody UserDeleteRequestDto request) {
        log.info("Request received: delete users by filter, email={}, username={}, role={}",
                request.getEmail(), request.getUsername(), request.getRole());
        long deletedCount = userService.deleteByFilter(request);
        log.info("Delete by filter completed: deleted {} users", deletedCount);
        return ResponseEntity.ok(deletedCount);
    }
}