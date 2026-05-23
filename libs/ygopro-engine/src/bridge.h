#pragma once

// Prevent windows.h from defining min/max macros
#ifndef NOMINMAX
#define NOMINMAX
#endif

#include <cstdint>
#include <string>
#include <vector>
#include <functional>
#include <unordered_map>

// Include ygopro-core API headers
#include "ocgapi.h"
#include "ocgapi_types.h"
#include "ocgapi_constants.h"

// Game constants
namespace YGO {
    constexpr int DUEL_STATUS_END      = OCG_DUEL_STATUS_END;
    constexpr int DUEL_STATUS_AWAITING = OCG_DUEL_STATUS_AWAITING;
    constexpr int DUEL_STATUS_CONTINUE = OCG_DUEL_STATUS_CONTINUE;
}

// Card database entry
struct CardEntry {
    uint32_t code;
    uint32_t alias;
    std::vector<uint16_t> setcodes;
    uint32_t type;
    uint32_t level;
    uint32_t attribute;
    uint64_t race;
    int32_t attack;
    int32_t defense;
    uint32_t lscale;
    uint32_t rscale;
    uint32_t link_marker;
};

// Duel state
struct DuelState {
    OCG_Duel handle = nullptr;
    int player_count[2] = {0, 0};
    std::vector<uint32_t> deck[2];
    std::vector<uint32_t> extra[2];
    bool started = false;
    bool finished = false;
    int winner = -1;
    int turn = 0;
    int current_player = 0;  // 0-based
    int phase = 0;
};

// Bridge class: wraps ocgcore API
class DuelBridge {
public:
    DuelBridge();
    ~DuelBridge();

    bool init(const std::string& card_db_path, const std::string& scripts_path);
    bool create_duel(uint64_t seed, uint64_t flags = 0);
    void add_card(uint8_t team, uint32_t code, uint32_t loc, uint32_t seq = 0, uint32_t pos = 0);
    bool start_duel();
    void shuffle_deck(uint8_t playerid);
    int process();
    std::vector<uint8_t> get_messages();
    void set_response(const std::vector<uint8_t>& response);
    std::vector<uint8_t> query_field();
    std::vector<uint8_t> query_location(uint8_t team, uint32_t loc, uint32_t flags);
    uint32_t query_count(uint8_t team, uint32_t loc);
    bool load_script(const char* buf, uint32_t len, const char* name);
    void destroy_duel();
    const DuelState& get_state() const { return state_; }
    DuelState& get_state_mut() { return state_; }

private:
    DuelState state_;
    std::string scripts_path_;
    std::unordered_map<uint32_t, CardEntry> card_db_;

    bool load_global_script(const char* name);
    static void card_reader_callback(void* payload, uint32_t code, OCG_CardData* data);
    static int  script_reader_callback(void* payload, OCG_Duel duel, const char* name);
    static void log_callback(void* payload, const char* string, int type);
};
