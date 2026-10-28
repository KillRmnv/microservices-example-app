package com.microservices_example_app.users.controller;

import com.microservices_example_app.users.dto.*;
import com.microservices_example_app.users.service.UserService;
import com.microservices_example_app.users.util.SensitiveMask;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Slf4j
@RestController
@RequestMapping("/users")
@Tag(name = "Users", description = "User administration (ADMIN only)")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @Operation(summary = "List all users")
    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<UserResponseDto>> getAll() {
        log.info("Request received: get all users");
        List<UserResponseDto> users = userService.getAll();
        log.info("Successfully returned {} users", users.size());
        return ResponseEntity.ok(users);
    }

    @Operation(summary = "Get a user by id")
    @GetMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<UserResponseDto> getById(@Parameter(description = "User id") @PathVariable int id) {
        log.info("Request received: get user by id={}", id);
        UserResponseDto user = userService.getById(id);
        log.info("Successfully returned user with id={}", id);
        return ResponseEntity.ok(user);
    }

    @Operation(summary = "Get a user by email")
    @GetMapping("/by-email")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<UserResponseDto> getByEmail(@Parameter(description = "User email address") @RequestParam String email) {
        log.info("Request received: get user by email={}", SensitiveMask.maskEmail(email));
        UserResponseDto user = userService.getByEmail(email);
        log.info("Successfully returned user by email={}", SensitiveMask.maskEmail(email));
        return ResponseEntity.ok(user);
    }

    @Operation(summary = "List users with pagination")
    @GetMapping("/page")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<UserResponseDto>> getUsersByPage(
            @Parameter(description = "Zero-based page index") @RequestParam int page,
            @Parameter(description = "Page size") @RequestParam int size
    ) {
        log.info("Request received: get users by page, page={}, size={}", page, size);
        List<UserResponseDto> users = userService.getUsersByPage(page, size);
        log.info("Successfully returned {} users for page={}, size={}", users.size(), page, size);
        return ResponseEntity.ok(users);
    }

    @Operation(summary = "Search users by filter")
    @GetMapping("/search")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<UserResponseDto>> searchByFilter(@Valid @ModelAttribute UserSearchRequestDto filter) {
        log.info("Request received: search users by filter, email={}, username={}, role={}",
                SensitiveMask.maskEmail(filter.getEmail()), filter.getUsername(), filter.getRole());
        List<UserResponseDto> users = userService.searchByFilter(filter);
        log.info("Search completed: found {} users", users.size());
        return ResponseEntity.ok(users);
    }

    @Operation(summary = "Search users by filter with pagination")
    @GetMapping("/search/page")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<UserResponseDto>> searchByFilterWithPage(
            @Valid @ModelAttribute UserSearchRequestDto filter,
            @Parameter(description = "Zero-based page index") @RequestParam int page,
            @Parameter(description = "Page size") @RequestParam int size
    ) {
        log.info("Request received: search users by filter with paging, email={}, username={}, role={}, page={}, size={}",
                SensitiveMask.maskEmail(filter.getEmail()), filter.getUsername(), filter.getRole(), page, size);
        List<UserResponseDto> users = userService.searchByFilter(filter, page, size);
        log.info("Paged search completed: found {} users for page={}, size={}", users.size(), page, size);
        return ResponseEntity.ok(users);
    }

    @Operation(summary = "Update a user")
    @PutMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<UserResponseDto> updateUser(@Valid @RequestBody UserUpdateRequestDto request) {
        log.info("Request received: update user id={}", request.getId());
        UserResponseDto updated = userService.updateUserById(request);
        log.info("User updated successfully: id={}", request.getId());
        return ResponseEntity.ok(updated);
    }

    @Operation(summary = "Delete a user")
    @DeleteMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> deleteUser(@Valid @RequestBody UserDeleteRequestDto request) {
        log.info("Request received: delete user id={}", request.getId());
        userService.deleteUser(request);
        log.info("User deleted successfully: id={}", request.getId());
        return ResponseEntity.noContent().build();
    }

    @Operation(summary = "Delete users matching a filter")
    @DeleteMapping("/search")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Long> deleteByFilter(@Valid @RequestBody UserDeleteRequestDto request) {
        log.info("Request received: delete users by filter, email={}, username={}, role={}",
                SensitiveMask.maskEmail(request.getEmail()), request.getUsername(), request.getRole());
        long deletedCount = userService.deleteByFilter(request);
        log.info("Delete by filter completed: deleted {} users", deletedCount);
        return ResponseEntity.ok(deletedCount);
    }

    @Operation(summary = "Create a user as administrator")
    @PostMapping("/admin/create")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<UserResponseDto> createUserByAdmin(@Valid @RequestBody UserRegistrationRequestDto request) {
        log.info("Admin creating new user: email={}, username={}, role={}, isSystem={}",
                SensitiveMask.maskEmail(request.getEmail()), request.getUsername(), request.getRole(), request.getIsSystem());
        UserRegistrationDto registration = userService.register(
                request.getEmail(),
                request.getPassword(),
                request.getRole(),
                request.getUsername(),
                request.getIsSystem() != null ? request.getIsSystem() : false
        );
        UserResponseDto response = userService.getById(registration.getId());
        log.info("Admin successfully created user with id={}", registration.getId());
        return ResponseEntity.ok(response);
    }
}