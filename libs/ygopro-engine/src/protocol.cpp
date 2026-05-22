#include "protocol.h"
#include "ocgapi_constants.h"
#include <sstream>
#include <iostream>
#include <cstring>

ProtocolHandler::ProtocolHandler(DuelBridge& bridge) : bridge_(bridge) {}

json ProtocolHandler::handle_command(const json& cmd) {
    try {
        std::string command = cmd.value("cmd", "");

        if (command == "init")            return cmd_init(cmd);
        if (command == "get_state")       return cmd_get_state(cmd);
        if (command == "get_legal_moves") return cmd_get_legal_moves(cmd);
        if (command == "do_move")         return cmd_do_move(cmd);
        if (command == "respond_chain")   return cmd_respond_chain(cmd);
        if (command == "draw")            return cmd_draw(cmd);
        if (command == "reset")           return cmd_reset(cmd);
        if (command == "query_field")     return cmd_query_field(cmd);

        return {{"ok", false}, {"error", "unknown_command"}, {"reason", "Unknown command: " + command}};
    } catch (const std::exception& e) {
        return {{"ok", false}, {"error", "internal_error"}, {"reason", e.what()}};
    }
}

// Helper: read uint32_t from buffer at offset
static uint32_t read_u32(const std::vector<uint8_t>& buf, size_t& pos) {
    if (pos + 4 > buf.size()) return 0;
    uint32_t val;
    memcpy(&val, buf.data() + pos, 4);
    pos += 4;
    return val;
}

// Helper: read uint8_t from buffer at offset
static uint8_t read_u8(const std::vector<uint8_t>& buf, size_t& pos) {
    if (pos >= buf.size()) return 0;
    return buf[pos++];
}

// Helper: read uint16_t from buffer at offset
static uint16_t read_u16(const std::vector<uint8_t>& buf, size_t& pos) {
    if (pos + 2 > buf.size()) return 0;
    uint16_t val;
    memcpy(&val, buf.data() + pos, 2);
    pos += 2;
    return val;
}

// Helper: read uint64_t from buffer
static uint64_t read_u64(const std::vector<uint8_t>& buf, size_t& pos) {
    if (pos + 8 > buf.size()) { pos += 8; return 0; }
    uint64_t val;
    memcpy(&val, buf.data() + pos, 8);
    pos += 8;
    return val;
}

// Helper: read int32_t from buffer
static int32_t read_i32(const std::vector<uint8_t>& buf, size_t& pos) {
    if (pos + 4 > buf.size()) return 0;
    int32_t val;
    memcpy(&val, buf.data() + pos, 4);
    pos += 4;
    return val;
}

json ProtocolHandler::cmd_init(const json& params) {
    auto deck_p1 = params.value("deck_p1", std::vector<uint32_t>{});
    auto deck_p2 = params.value("deck_p2", std::vector<uint32_t>{});
    uint64_t seed = params.value("seed", 0ULL);
    uint64_t flags = params.value("flags", 0ULL);

    if (!bridge_.create_duel(seed, flags)) {
        return {{"ok", false}, {"error", "create_failed"}, {"reason", "Failed to create duel"}};
    }

    // Add cards to decks
    for (size_t i = 0; i < deck_p1.size(); i++) {
        bridge_.add_card(0, deck_p1[i], LOCATION_DECK, static_cast<uint32_t>(i));
    }
    for (size_t i = 0; i < deck_p2.size(); i++) {
        bridge_.add_card(1, deck_p2[i], LOCATION_DECK, static_cast<uint32_t>(i));
    }

    if (!bridge_.start_duel()) {
        return {{"ok", false}, {"error", "start_failed"}, {"reason", "Failed to start duel"}};
    }

    // Process initial steps until engine needs input
    int status = YGO::DUEL_STATUS_CONTINUE;
    while (status == YGO::DUEL_STATUS_CONTINUE) {
        status = bridge_.process();
    }

    // Get messages after initial processing and cache them
    cached_messages_ = bridge_.get_messages();
    json events = parse_messages(cached_messages_);

    return {{"ok", true}, {"data", {{"status", status}, {"events", events}}}};
}

json ProtocolHandler::cmd_get_state(const json& params) {
    int player_pov = params.value("player_pov", 1);

    auto state = bridge_.get_state();
    if (!state.handle) {
        return {{"ok", false}, {"error", "no_duel"}, {"reason", "No active duel"}};
    }

    return {{"ok", true}, {"data", serialize_state()}};
}

json ProtocolHandler::cmd_get_legal_moves(const json& params) {
    auto state = bridge_.get_state();
    if (!state.handle) {
        return {{"ok", false}, {"error", "no_duel"}};
    }

    // Use cached messages (get_messages() clears the buffer, so we cache after each process)
    json moves = parse_legal_moves(cached_messages_);

    return {{"ok", true}, {"data", {{"moves", moves}, {"raw_size", cached_messages_.size()}}}};
}

json ProtocolHandler::cmd_do_move(const json& params) {
    auto state = bridge_.get_state();
    if (!state.handle) {
        return {{"ok", false}, {"error", "no_duel"}};
    }

    json move = params.value("move", json{});
    std::string move_type = move.value("type", "");
    if (move_type.empty()) {
        move_type = params.value("move_type", "");
    }



    // Convert move to engine response bytes
    std::vector<uint8_t> response;

    if (move_type == "summon" || move_type == "spsummon" || move_type == "reposition" ||
        move_type == "mset" || move_type == "sset" || move_type == "activate" ||
        move_type == "to_bp" || move_type == "to_ep") {
        // For SELECT_IDLECMD: response is a 32-bit integer: (index << 16) | type
        // type: 0=summon, 1=spsummon, 2=reposition, 3=mset, 4=sset, 5=activate, 6=to_bp, 7=to_ep
        static const std::map<std::string, uint32_t> type_map = {
            {"summon", 0}, {"spsummon", 1}, {"reposition", 2},
            {"mset", 3}, {"sset", 4}, {"activate", 5},
            {"to_bp", 6}, {"to_ep", 7}
        };
        auto it = type_map.find(move_type);
        if (it != type_map.end()) {
            int index = move.value("index", move.value("source_idx", 0));
            uint32_t val = it->second | (static_cast<uint32_t>(index) << 16);
            response.push_back(val & 0xFF);
            response.push_back((val >> 8) & 0xFF);
            response.push_back((val >> 16) & 0xFF);
            response.push_back((val >> 24) & 0xFF);
        }
    } else if (move_type == "attack" || move_type == "attack_direct" || move_type == "to_m2" || move_type == "to_ep_battle") {
        // For SELECT_BATTLECMD: response is a 32-bit integer: (index << 16) | type
        static const std::map<std::string, uint32_t> battle_map = {
            {"attack", 0}, {"attack_direct", 1}, {"to_m2", 2}, {"to_ep_battle", 3}
        };
        auto it = battle_map.find(move_type);
        if (it != battle_map.end()) {
            int index = move.value("index", move.value("source_idx", 0));
            uint32_t val = it->second | (static_cast<uint32_t>(index) << 16);
            response.push_back(val & 0xFF);
            response.push_back((val >> 8) & 0xFF);
            response.push_back((val >> 16) & 0xFF);
            response.push_back((val >> 24) & 0xFF);
        }
    } else if (move_type == "yes") {
        // SELECT_EFFECTYN / SELECT_YESNO: int32_t = 1
        uint32_t val = 1;
        response.push_back(val & 0xFF);
        response.push_back((val >> 8) & 0xFF);
        response.push_back((val >> 16) & 0xFF);
        response.push_back((val >> 24) & 0xFF);
    } else if (move_type == "no") {
        // SELECT_EFFECTYN / SELECT_YESNO: int32_t = 0
        uint32_t val = 0;
        response.push_back(val & 0xFF);
        response.push_back((val >> 8) & 0xFF);
        response.push_back((val >> 16) & 0xFF);
        response.push_back((val >> 24) & 0xFF);
    } else if (move_type == "select") {
        // SELECT_CARD / SELECT_TRIBUTE: [type(int32)] + [count(uint32)] + [indices...]
        // type 0 = uint32_t indices, type 1 = uint16_t, type 2 = uint8_t
        // We use type 2 (uint8_t) for compactness
        uint32_t type_val = 2;
        response.push_back(type_val & 0xFF);
        response.push_back((type_val >> 8) & 0xFF);
        response.push_back((type_val >> 16) & 0xFF);
        response.push_back((type_val >> 24) & 0xFF);
        auto indices = move.value("indices", std::vector<int>{});
        uint32_t count = static_cast<uint32_t>(indices.size());
        response.push_back(count & 0xFF);
        response.push_back((count >> 8) & 0xFF);
        response.push_back((count >> 16) & 0xFF);
        response.push_back((count >> 24) & 0xFF);
        for (int idx : indices) {
            response.push_back(static_cast<uint8_t>(idx));
        }
    } else if (move_type == "option") {
        // SELECT_OPTION: int32_t = option index
        uint32_t val = static_cast<uint32_t>(move.value("option", 0));
        response.push_back(val & 0xFF);
        response.push_back((val >> 8) & 0xFF);
        response.push_back((val >> 16) & 0xFF);
        response.push_back((val >> 24) & 0xFF);
    } else if (move_type == "place") {
        // SELECT_PLACE: [player(uint8)] + [location(uint8)] + [sequence(uint8)] repeated count times
        // count comes from the SELECT_PLACE prompt (how many zones to select)
        int count = move.value("count", 1);
        int player = move.value("player", 0);
        int location = move.value("location", 0);
        int sequence = move.value("sequence", 0);
        // If locations/sequences are provided as arrays, use them; otherwise repeat the single values
        auto locations = move.value("locations", std::vector<int>{});
        auto sequences = move.value("sequences", std::vector<int>{});
        for (int i = 0; i < count; i++) {
            response.push_back(static_cast<uint8_t>(player));
            response.push_back(static_cast<uint8_t>(locations.empty() ? location : locations[i]));
            response.push_back(static_cast<uint8_t>(sequences.empty() ? sequence : sequences[i]));
        }
    } else if (move_type == "position") {
        // SELECT_POSITION: int32_t = position bitmask
        uint32_t val = static_cast<uint32_t>(move.value("position", 1));
        response.push_back(val & 0xFF);
        response.push_back((val >> 8) & 0xFF);
        response.push_back((val >> 16) & 0xFF);
        response.push_back((val >> 24) & 0xFF);
    } else if (move_type == "chain") {
        // SELECT_CHAIN: int32_t = chain index (-1 to pass)
        uint32_t val = static_cast<uint32_t>(move.value("index", -1));
        response.push_back(val & 0xFF);
        response.push_back((val >> 8) & 0xFF);
        response.push_back((val >> 16) & 0xFF);
        response.push_back((val >> 24) & 0xFF);
    } else if (move_type == "counter") {
        // SELECT_COUNTER: each index is uint8_t
        auto indices = move.value("indices", std::vector<int>{});
        for (int idx : indices) {
            response.push_back(static_cast<uint8_t>(idx));
        }
    } else if (move_type == "sort") {
        // SORT_CARD: each index is int32_t
        auto indices = move.value("indices", std::vector<int>{});
        for (int idx : indices) {
            uint32_t val = static_cast<uint32_t>(idx);
            response.push_back(val & 0xFF);
            response.push_back((val >> 8) & 0xFF);
            response.push_back((val >> 16) & 0xFF);
            response.push_back((val >> 24) & 0xFF);
        }
    } else if (move_type == "announce") {
        uint32_t value = move.value("value", 0);
        response.push_back(value & 0xFF);
        response.push_back((value >> 8) & 0xFF);
        response.push_back((value >> 16) & 0xFF);
        response.push_back((value >> 24) & 0xFF);
    } else {
        return {{"ok", false}, {"error", "invalid_move_type"}, {"reason", "Unknown move_type: " + move_type}};
    }

    if (response.empty()) {
        return {{"ok", false}, {"error", "empty_response"}, {"reason", "Failed to build response"}};
    }

    // Send response to engine
    bridge_.set_response(response);

    // Process until next AWAITING or END, accumulating messages
    std::vector<uint8_t> all_messages;
    int status = YGO::DUEL_STATUS_CONTINUE;
    while (status == YGO::DUEL_STATUS_CONTINUE) {
        status = bridge_.process();
        auto msgs = bridge_.get_messages();
        all_messages.insert(all_messages.end(), msgs.begin(), msgs.end());
    }

    // Also get any remaining messages after final process
    auto final_msgs = bridge_.get_messages();
    all_messages.insert(all_messages.end(), final_msgs.begin(), final_msgs.end());

    // Cache and parse all accumulated messages
    cached_messages_ = std::move(all_messages);

    // Check for MSG_RETRY (type 1) - engine rejected the response
    if (cached_messages_.size() >= 5) {
        uint32_t msg_size = 0;
        memcpy(&msg_size, cached_messages_.data(), 4);
        if (msg_size == 1 && cached_messages_.size() >= 5 && cached_messages_[4] == 1) {
            // MSG_RETRY - re-read the prompt from engine
            // The engine is still waiting for valid input, so re-fetch messages
            cached_messages_ = bridge_.get_messages();
            return {{"ok", false}, {"error", "retry"}, {"reason", "Engine rejected the move (MSG_RETRY). The move may be illegal."}};
        }
    }

    json events = parse_messages(cached_messages_);
    json next_moves = parse_legal_moves(cached_messages_);

    json result;
    result["status"] = status;
    result["events"] = events;
    result["next_moves"] = next_moves;
    result["game_over"] = (status == YGO::DUEL_STATUS_END);

    // Debug: include raw message hex
    {
        std::string hex;
        hex.reserve(cached_messages_.size() * 2);
        for (uint8_t b : cached_messages_) {
            char buf[3];
            snprintf(buf, sizeof(buf), "%02x", b);
            hex += buf;
        }
        result["debug_hex"] = hex;
        result["debug_size"] = cached_messages_.size();
    }

    return {{"ok", true}, {"data", result}};
}

json ProtocolHandler::cmd_respond_chain(const json& params) {
    auto state = bridge_.get_state();
    if (!state.handle) {
        return {{"ok", false}, {"error", "no_duel"}};
    }

    std::string action = params.value("action", "pass");

    std::vector<uint8_t> response;
    // For SELECT_CHAIN: -1 (0xFFFFFFFF) to pass, 0+ to activate a chain
    // For SELECT_EFFECTYN/YESNO: 1=yes, 0=no
    int32_t val;
    if (action == "activate" || action == "yes") {
        val = 1;
    } else if (action == "pass" || action == "no") {
        val = -1; // Pass for chain, will be 0 for yes/no (close enough - engine validates)
    } else {
        val = 0;
    }
    uint32_t uval = static_cast<uint32_t>(val);
    response.push_back(uval & 0xFF);
    response.push_back((uval >> 8) & 0xFF);
    response.push_back((uval >> 16) & 0xFF);
    response.push_back((uval >> 24) & 0xFF);

    bridge_.set_response(response);

    std::vector<uint8_t> all_messages;
    int status = YGO::DUEL_STATUS_CONTINUE;
    while (status == YGO::DUEL_STATUS_CONTINUE) {
        status = bridge_.process();
        auto msgs = bridge_.get_messages();
        all_messages.insert(all_messages.end(), msgs.begin(), msgs.end());
    }
    auto final_msgs = bridge_.get_messages();
    all_messages.insert(all_messages.end(), final_msgs.begin(), final_msgs.end());

    cached_messages_ = std::move(all_messages);
    json events = parse_messages(cached_messages_);
    json next_moves = parse_legal_moves(cached_messages_);

    return {{"ok", true}, {"data", {{"status", status}, {"events", events}, {"next_moves", next_moves}}}};
}

json ProtocolHandler::cmd_draw(const json& params) {
    auto state = bridge_.get_state();
    if (!state.handle) {
        return {{"ok", false}, {"error", "no_duel"}};
    }

    // Draw is typically handled automatically by the engine during DP
    return {{"ok", true}, {"data", {{"message", "Draw is handled by engine"}}}};
}

json ProtocolHandler::cmd_reset(const json& params) {
    bridge_.destroy_duel();
    return {{"ok", true}, {"data", {{"message", "Duel reset"}}}};
}

json ProtocolHandler::cmd_query_field(const json& params) {
    auto state = bridge_.get_state();
    if (!state.handle) {
        return {{"ok", false}, {"error", "no_duel"}};
    }

    auto data = bridge_.query_field();
    return {{"ok", true}, {"data", serialize_query_data(data)}};
}

// Parse message buffer into a list of event objects
// Buffer format: [uint32_t size][message payload of size bytes] repeated
json ProtocolHandler::parse_messages(const std::vector<uint8_t>& buf) {
    json events = json::array();
    size_t pos = 0;

    while (pos < buf.size()) {
        // Read 4-byte size prefix
        uint32_t msg_size = read_u32(buf, pos);
        if (msg_size == 0 || pos + msg_size > buf.size()) break;
        size_t msg_end = pos + msg_size;

        uint8_t msg_type = read_u8(buf, pos);
        json event;
        event["type"] = msg_type;

        switch (msg_type) {
            case MSG_WIN: {
                uint8_t winner = read_u8(buf, pos);
                uint8_t reason = read_u8(buf, pos);
                event["winner"] = winner;
                event["reason"] = reason;
                break;
            }
            case MSG_NEW_TURN: {
                uint8_t player = read_u8(buf, pos);
                event["player"] = player;
                break;
            }
            case MSG_NEW_PHASE: {
                uint16_t phase = static_cast<uint16_t>(read_u32(buf, pos));
                event["phase"] = phase;
                break;
            }
            case MSG_DRAW: {
                uint8_t player = read_u8(buf, pos);
                uint32_t count = read_u32(buf, pos);
                event["player"] = player;
                event["count"] = count;
                json cards = json::array();
                for (uint32_t i = 0; i < count; i++) {
                    cards.push_back(read_u32(buf, pos));
                }
                event["cards"] = cards;
                break;
            }
            case MSG_MOVE: {
                uint32_t code = read_u32(buf, pos);
                uint8_t pc = read_u8(buf, pos);
                uint8_t pl = read_u8(buf, pos);
                uint8_t ps = read_u8(buf, pos);
                uint8_t pp = read_u8(buf, pos);
                uint8_t cc = read_u8(buf, pos);
                uint8_t cl = read_u8(buf, pos);
                uint8_t cs = read_u8(buf, pos);
                uint8_t cp = read_u8(buf, pos);
                uint32_t reason = read_u32(buf, pos);
                event["code"] = code;
                event["from"] = {{"controller", pc}, {"location", pl}, {"sequence", ps}, {"position", pp}};
                event["to"] = {{"controller", cc}, {"location", cl}, {"sequence", cs}, {"position", cp}};
                event["reason"] = reason;
                break;
            }
            case MSG_SUMMONING:
            case MSG_SPSUMMONING:
            case MSG_FLIPSUMMONING: {
                uint32_t code = read_u32(buf, pos);
                event["code"] = code;
                // Skip card location info (8 bytes)
                read_u32(buf, pos);
                read_u32(buf, pos);
                break;
            }
            case MSG_CHAINING: {
                uint32_t code = read_u32(buf, pos);
                event["code"] = code;
                // Skip card location + chain info
                for (int i = 0; i < 6; i++) read_u32(buf, pos);
                break;
            }
            case MSG_CHAIN_SOLVING:
            case MSG_CHAIN_SOLVED:
            case MSG_CHAIN_END: {
                read_u8(buf, pos); // chain count
                break;
            }
            case MSG_HINT: {
                read_u8(buf, pos); // hint type
                read_u8(buf, pos); // player
                read_u32(buf, pos); // value
                break;
            }
            case MSG_SHUFFLE_DECK:
            case MSG_SHUFFLE_HAND: {
                read_u8(buf, pos); // player
                break;
            }
            case MSG_CONFIRM_DECKTOP:
            case MSG_CONFIRM_CARDS: {
                uint8_t player = read_u8(buf, pos);
                uint32_t count = read_u32(buf, pos);
                event["player"] = player;
                for (uint32_t i = 0; i < count; i++) {
                    read_u32(buf, pos); // card code
                    read_u32(buf, pos); // location info
                }
                break;
            }
            case MSG_CARD_SELECTED: {
                uint8_t player = read_u8(buf, pos);
                uint32_t count = read_u32(buf, pos);
                for (uint32_t i = 0; i < count; i++) {
                    read_u32(buf, pos);
                }
                break;
            }
            // Selection prompts - these are always the last message in the buffer.
            // We mark them as prompts and stop parsing (remaining bytes belong to the prompt).
            case MSG_SELECT_IDLECMD:
            case MSG_SELECT_BATTLECMD:
            case MSG_SELECT_EFFECTYN:
            case MSG_SELECT_YESNO:
            case MSG_SELECT_OPTION:
            case MSG_SELECT_CARD:
            case MSG_SELECT_CHAIN:
            case MSG_SELECT_PLACE:
            case MSG_SELECT_POSITION:
            case MSG_SELECT_TRIBUTE:
            case MSG_SELECT_COUNTER:
            case MSG_SELECT_SUM:
            case MSG_SELECT_DISFIELD:
            case MSG_SELECT_UNSELECT_CARD:
            case MSG_SORT_CARD:
            case MSG_SORT_CHAIN: {
                event["is_prompt"] = true;
                events.push_back(event);
                // Stop parsing - prompt data will be parsed by parse_legal_moves
                return events;
            }
            default: {
                // Unknown message type - skip to next message
                break;
            }
        }

        // Advance to end of this message frame
        pos = msg_end;
        events.push_back(event);
    }

    return events;
}

// Parse message buffer to extract legal moves
json ProtocolHandler::parse_legal_moves(const std::vector<uint8_t>& buf) {
    json moves = json::array();
    size_t pos = 0;

    // Find the last prompt message in the buffer
    json last_prompt;
    size_t last_prompt_pos = 0;

    while (pos < buf.size()) {
        // Read 4-byte size prefix
        uint32_t msg_size = read_u32(buf, pos);
        if (msg_size == 0 || pos + msg_size > buf.size()) break;
        size_t msg_end = pos + msg_size;

        size_t msg_start = pos;
        uint8_t msg_type = read_u8(buf, pos);

        switch (msg_type) {
            case MSG_SELECT_IDLECMD: {
                uint8_t player = read_u8(buf, pos);
                // summon: code(4)+ctrl(1)+loc(1)+seq(4) = 10 bytes each
                uint32_t summon_count = read_u32(buf, pos);
                for (uint32_t i = 0; i < summon_count; i++) { read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); }
                // spsummon: code(4)+ctrl(1)+loc(1)+seq(4) = 10 bytes each
                uint32_t spsummon_count = read_u32(buf, pos);
                for (uint32_t i = 0; i < spsummon_count; i++) { read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); }
                // reposition: code(4)+ctrl(1)+loc(1)+seq(1) = 7 bytes each
                uint32_t repos_count = read_u32(buf, pos);
                for (uint32_t i = 0; i < repos_count; i++) { read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); }
                // mset: code(4)+ctrl(1)+loc(1)+seq(4) = 10 bytes each
                uint32_t mset_count = read_u32(buf, pos);
                for (uint32_t i = 0; i < mset_count; i++) { read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); }
                // sset: code(4)+ctrl(1)+loc(1)+seq(4) = 10 bytes each
                uint32_t sset_count = read_u32(buf, pos);
                for (uint32_t i = 0; i < sset_count; i++) { read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); }
                // activate: code(4)+ctrl(1)+loc(1)+seq(4)+desc(8)+mode(1) = 19 bytes each
                uint32_t activate_count = read_u32(buf, pos);
                for (uint32_t i = 0; i < activate_count; i++) { read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); read_u32(buf, pos); read_u32(buf, pos); read_u8(buf, pos); }
                // to_bp, to_ep, can_shuffle flags
                uint8_t to_bp = read_u8(buf, pos);
                uint8_t to_ep = read_u8(buf, pos);
                uint8_t can_shuffle = read_u8(buf, pos);

                last_prompt = {
                    {"type", "idlecmd"},
                    {"player", player},
                    {"summon_count", summon_count},
                    {"spsummon_count", spsummon_count},
                    {"reposition_count", repos_count},
                    {"mset_count", mset_count},
                    {"sset_count", sset_count},
                    {"activate_count", activate_count},
                    {"to_bp", to_bp},
                    {"to_ep", to_ep},
                    {"can_shuffle", can_shuffle}
                };
                last_prompt_pos = msg_start;
                break;
            }
            case MSG_SELECT_BATTLECMD: {
                uint8_t player = read_u8(buf, pos);
                // attack: code(4)+ctrl(1)+loc(1)+seq(4) = 10 bytes each
                uint32_t attack_count = read_u32(buf, pos);
                for (uint32_t i = 0; i < attack_count; i++) { read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); }
                // activate: code(4)+ctrl(1)+loc(1)+seq(4)+desc(8)+mode(1) = 19 bytes each
                uint32_t activate_count = read_u32(buf, pos);
                for (uint32_t i = 0; i < activate_count; i++) { read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); read_u32(buf, pos); read_u32(buf, pos); read_u8(buf, pos); }
                // to_m2, to_ep flags
                uint8_t to_m2 = read_u8(buf, pos);
                uint8_t to_ep = read_u8(buf, pos);

                last_prompt = {
                    {"type", "battlecmd"},
                    {"player", player},
                    {"attack_count", attack_count},
                    {"activate_count", activate_count},
                    {"to_m2", to_m2},
                    {"to_ep", to_ep}
                };
                last_prompt_pos = msg_start;
                break;
            }
            case MSG_SELECT_EFFECTYN: {
                uint8_t player = read_u8(buf, pos);
                uint32_t code = read_u32(buf, pos);
                uint8_t controller = read_u8(buf, pos);
                uint8_t location = read_u8(buf, pos);
                uint32_t sequence = read_u32(buf, pos);
                // description (8 bytes)
                read_u32(buf, pos);
                read_u32(buf, pos);
                last_prompt = {{"type", "effectyn"}, {"player", player}, {"code", code}, {"controller", controller}, {"location", location}, {"sequence", sequence}};
                last_prompt_pos = msg_start;
                break;
            }
            case MSG_SELECT_YESNO: {
                uint8_t player = read_u8(buf, pos);
                uint32_t desc = read_u32(buf, pos);
                last_prompt = {{"type", "yesno"}, {"player", player}, {"description", desc}};
                last_prompt_pos = msg_start;
                break;
            }
            case MSG_SELECT_OPTION: {
                uint8_t player = read_u8(buf, pos);
                uint32_t count = read_u32(buf, pos);
                json options = json::array();
                for (uint32_t i = 0; i < count; i++) {
                    options.push_back(read_u32(buf, pos));
                }
                last_prompt = {{"type", "option"}, {"player", player}, {"options", options}};
                last_prompt_pos = msg_start;
                break;
            }
            case MSG_SELECT_CARD: {
                uint8_t player = read_u8(buf, pos);
                uint8_t cancelable = read_u8(buf, pos);
                uint32_t min_count = read_u32(buf, pos);
                uint32_t max_count = read_u32(buf, pos);
                uint32_t count = read_u32(buf, pos);
                json cards = json::array();
                for (uint32_t i = 0; i < count; i++) {
                    uint32_t code = read_u32(buf, pos);
                    uint8_t controller = read_u8(buf, pos);
                    uint8_t location = read_u8(buf, pos);
                    uint32_t sequence = read_u32(buf, pos);
                    uint32_t position = read_u32(buf, pos);
                    cards.push_back({{"code", code}, {"controller", controller}, {"location", location}, {"sequence", sequence}});
                }
                last_prompt = {
                    {"type", "select_card"}, {"player", player},
                    {"cancelable", cancelable}, {"min", min_count}, {"max", max_count},
                    {"cards", cards}
                };
                last_prompt_pos = msg_start;
                break;
            }
            case MSG_SELECT_CHAIN: {
                uint8_t player = read_u8(buf, pos);
                uint8_t spe_count = read_u8(buf, pos);
                uint8_t forced = read_u8(buf, pos);
                read_u32(buf, pos); // hint_timing[0]
                read_u32(buf, pos); // hint_timing[1]
                uint32_t count = read_u32(buf, pos);
                json chains = json::array();
                for (uint32_t i = 0; i < count; i++) {
                    uint32_t code = read_u32(buf, pos);
                    // get_info_location: ctrl(1) + loc(1) + seq(4) + pos(4) = 10 bytes
                    uint8_t ctrl = read_u8(buf, pos);
                    uint8_t loc = read_u8(buf, pos);
                    uint32_t seq = read_u32(buf, pos);
                    uint32_t position = read_u32(buf, pos);
                    read_u64(buf, pos); // description (8 bytes)
                    read_u8(buf, pos);  // client_mode
                    chains.push_back({{"code", code}, {"controller", ctrl}, {"location", loc}, {"sequence", seq}});
                }
                last_prompt = {
                    {"type", "select_chain"}, {"player", player},
                    {"spe_count", spe_count}, {"forced", forced},
                    {"count", count}, {"chains", chains}
                };
                last_prompt_pos = msg_start;
                break;
            }
            case MSG_SELECT_PLACE:
            case MSG_SELECT_DISFIELD: {
                uint8_t player = read_u8(buf, pos);
                uint8_t count = read_u8(buf, pos);
                uint32_t flag = read_u32(buf, pos);
                last_prompt = {{"type", "select_place"}, {"player", player}, {"count", count}, {"flag", flag}};
                last_prompt_pos = msg_start;
                break;
            }
            case MSG_SELECT_POSITION: {
                uint8_t player = read_u8(buf, pos);
                uint32_t code = read_u32(buf, pos);
                uint32_t positions = read_u32(buf, pos);
                last_prompt = {{"type", "select_position"}, {"player", player}, {"code", code}, {"positions", positions}};
                last_prompt_pos = msg_start;
                break;
            }
            case MSG_SELECT_TRIBUTE: {
                uint8_t player = read_u8(buf, pos);
                uint32_t cancelable = read_u32(buf, pos);
                uint32_t min_count = read_u32(buf, pos);
                uint32_t max_count = read_u32(buf, pos);
                uint32_t count = read_u32(buf, pos);
                json cards = json::array();
                for (uint32_t i = 0; i < count; i++) {
                    uint32_t code = read_u32(buf, pos);
                    uint32_t loc = read_u32(buf, pos);
                    cards.push_back({{"code", code}, {"location", loc}});
                }
                last_prompt = {
                    {"type", "select_tribute"}, {"player", player},
                    {"cancelable", cancelable}, {"min", min_count}, {"max", max_count},
                    {"cards", cards}
                };
                last_prompt_pos = msg_start;
                break;
            }
            case MSG_SELECT_COUNTER: {
                uint8_t player = read_u8(buf, pos);
                uint16_t counter_type = static_cast<uint16_t>(read_u32(buf, pos));
                uint32_t count = read_u32(buf, pos);
                last_prompt = {{"type", "select_counter"}, {"player", player}, {"counter_type", counter_type}, {"count", count}};
                last_prompt_pos = msg_start;
                break;
            }
            case MSG_SELECT_SUM: {
                read_u8(buf, pos); // mode
                read_u8(buf, pos); // player
                read_u32(buf, pos); // sumval
                uint32_t count = read_u32(buf, pos);
                last_prompt = {{"type", "select_sum"}};
                last_prompt_pos = msg_start;
                for (uint32_t i = 0; i < count; i++) { read_u32(buf, pos); read_u32(buf, pos); read_u32(buf, pos); }
                break;
            }
            case MSG_SORT_CARD: {
                uint8_t player = read_u8(buf, pos);
                uint32_t count = read_u32(buf, pos);
                last_prompt = {{"type", "sort_card"}, {"player", player}, {"count", count}};
                last_prompt_pos = msg_start;
                for (uint32_t i = 0; i < count; i++) { read_u32(buf, pos); read_u32(buf, pos); }
                break;
            }
            case MSG_SELECT_UNSELECT_CARD: {
                uint8_t player = read_u8(buf, pos);
                uint32_t finishable = read_u32(buf, pos);
                uint32_t cancelable = read_u32(buf, pos);
                uint32_t min_count = read_u32(buf, pos);
                uint32_t max_count = read_u32(buf, pos);
                uint32_t count1 = read_u32(buf, pos);
                for (uint32_t i = 0; i < count1; i++) { read_u32(buf, pos); read_u32(buf, pos); }
                uint32_t count2 = read_u32(buf, pos);
                for (uint32_t i = 0; i < count2; i++) { read_u32(buf, pos); read_u32(buf, pos); }
                last_prompt = {{"type", "select_unselect_card"}, {"player", player}};
                last_prompt_pos = msg_start;
                break;
            }
            // Non-prompt messages: skip their data so pos advances
            case MSG_WIN: { read_u8(buf, pos); read_u8(buf, pos); break; }
            case MSG_NEW_TURN: { read_u8(buf, pos); break; }
            case MSG_NEW_PHASE: { read_u32(buf, pos); break; }
            case MSG_DRAW: {
                read_u8(buf, pos);
                uint32_t cnt = read_u32(buf, pos);
                for (uint32_t i = 0; i < cnt; i++) read_u32(buf, pos);
                break;
            }
            case MSG_MOVE: {
                read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos);
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos);
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos);
                read_u32(buf, pos);
                break;
            }
            case MSG_POS_CHANGE: {
                read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos);
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos);
                break;
            }
            case MSG_SET: { read_u32(buf, pos); read_u32(buf, pos); break; }
            case MSG_SWAP: {
                read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos);
                read_u8(buf, pos); read_u8(buf, pos);
                read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos);
                read_u8(buf, pos); read_u8(buf, pos);
                break;
            }
            case MSG_SUMMONING: case MSG_FLIPSUMMONING: case MSG_SPSUMMONING: {
                read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos);
                read_u8(buf, pos); read_u8(buf, pos);
                break;
            }
            case MSG_SUMMONED: case MSG_FLIPSUMMONED: case MSG_SPSUMMONED: break;
            case MSG_CHAINING: {
                read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos);
                read_u8(buf, pos); read_u32(buf, pos); read_u32(buf, pos);
                read_u8(buf, pos); read_u8(buf, pos);
                break;
            }
            case MSG_CHAINED: case MSG_CHAIN_SOLVING: case MSG_CHAIN_SOLVED:
            case MSG_CHAIN_END: case MSG_CHAIN_NEGATED: case MSG_CHAIN_DISABLED: {
                read_u8(buf, pos); break;
            }
            case MSG_CARD_SELECTED: case MSG_RANDOM_SELECTED: {
                read_u8(buf, pos);
                uint32_t cnt = read_u32(buf, pos);
                for (uint32_t i = 0; i < cnt; i++) read_u32(buf, pos);
                break;
            }
            case MSG_BECOME_TARGET: case MSG_BE_CHAIN_TARGET: {
                uint32_t cnt = read_u32(buf, pos);
                for (uint32_t i = 0; i < cnt; i++) {
                    read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                }
                break;
            }
            case MSG_DAMAGE: case MSG_RECOVER: case MSG_PAY_LPCOST: {
                read_u8(buf, pos); read_u32(buf, pos); break;
            }
            case MSG_LPUPDATE: { read_u8(buf, pos); read_u32(buf, pos); break; }
            case MSG_EQUIP: {
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                break;
            }
            case MSG_UNEQUIP: {
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                break;
            }
            case MSG_CARD_TARGET: case MSG_CANCEL_TARGET: {
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                break;
            }
            case MSG_ADD_COUNTER: case MSG_REMOVE_COUNTER: {
                read_u16(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                break;
            }
            case MSG_ATTACK: {
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                break;
            }
            case MSG_BATTLE: {
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                read_u32(buf, pos); read_u32(buf, pos);
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                read_u32(buf, pos); read_u32(buf, pos);
                break;
            }
            case MSG_ATTACK_DISABLED: case MSG_DAMAGE_STEP_START: case MSG_DAMAGE_STEP_END: break;
            case MSG_MISSED_EFFECT: { read_u32(buf, pos); read_u32(buf, pos); break; }
            case MSG_CREATE_RELATION: case MSG_RELEASE_RELATION: {
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                break;
            }
            case MSG_TOSS_COIN: case MSG_TOSS_DICE: {
                read_u8(buf, pos);
                uint32_t cnt = read_u32(buf, pos);
                for (uint32_t i = 0; i < cnt; i++) read_u8(buf, pos);
                break;
            }
            case MSG_ROCK_PAPER_SCISSORS: { read_u8(buf, pos); break; }
            case MSG_HAND_RES: { read_u8(buf, pos); read_u8(buf, pos); break; }
            case MSG_ANNOUNCE_RACE: case MSG_ANNOUNCE_ATTRIB: { read_u8(buf, pos); read_u32(buf, pos); read_u32(buf, pos); break; }
            case MSG_ANNOUNCE_CARD: case MSG_ANNOUNCE_NUMBER: {
                read_u8(buf, pos);
                uint32_t cnt = read_u32(buf, pos);
                for (uint32_t i = 0; i < cnt; i++) read_u32(buf, pos);
                break;
            }
            case MSG_HINT: { read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); read_u8(buf, pos); break; }
            case MSG_WAITING: break;
            case MSG_START: { read_u8(buf, pos); read_u32(buf, pos); read_u32(buf, pos); break; }
            case MSG_CONFIRM_DECKTOP: case MSG_CONFIRM_CARDS: {
                read_u8(buf, pos);
                uint32_t cnt = read_u32(buf, pos);
                for (uint32_t i = 0; i < cnt; i++) {
                    read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                }
                break;
            }
            case MSG_SHUFFLE_DECK: case MSG_SHUFFLE_HAND: case MSG_SHUFFLE_EXTRA:
            case MSG_REFRESH_DECK: case MSG_SHUFFLE_SET_CARD: case MSG_REVERSE_DECK: {
                read_u8(buf, pos); break;
            }
            case MSG_SWAP_GRAVE_DECK: case MSG_DECK_TOP: { read_u8(buf, pos); break; }
            case MSG_FIELD_DISABLED: { read_u32(buf, pos); break; }
            case MSG_CARD_HINT: { read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); read_u8(buf, pos); break; }
            case MSG_PLAYER_HINT: { read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); break; }
            case MSG_TAG_SWAP: {
                read_u8(buf, pos);
                read_u32(buf, pos); read_u32(buf, pos); read_u32(buf, pos); read_u32(buf, pos);
                uint32_t cnt = read_u32(buf, pos);
                for (uint32_t i = 0; i < cnt; i++) read_u32(buf, pos);
                cnt = read_u32(buf, pos);
                for (uint32_t i = 0; i < cnt; i++) read_u32(buf, pos);
                cnt = read_u32(buf, pos);
                for (uint32_t i = 0; i < cnt; i++) read_u32(buf, pos);
                break;
            }
            case MSG_RELOAD_FIELD: {
                read_u32(buf, pos);
                for (int p = 0; p < 2; p++) {
                    read_u32(buf, pos); read_u32(buf, pos); read_u32(buf, pos);
                    for (int z = 0; z < 5; z++) { read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); }
                    read_u32(buf, pos); read_u32(buf, pos);
                    for (int z = 0; z < 8; z++) { read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); }
                    read_u32(buf, pos);
                    for (int z = 0; z < 2; z++) { read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos); }
                }
                { uint32_t cnt = read_u32(buf, pos); for (uint32_t i = 0; i < cnt; i++) read_u32(buf, pos); }
                break;
            }
            case MSG_AI_NAME: case MSG_SHOW_HINT: {
                uint32_t len = read_u32(buf, pos);
                for (uint32_t i = 0; i < len; i++) read_u8(buf, pos);
                break;
            }
            case MSG_MATCH_KILL: { read_u32(buf, pos); break; }
            case MSG_CONFIRM_EXTRATOP: {
                read_u8(buf, pos);
                uint32_t cnt = read_u32(buf, pos);
                for (uint32_t i = 0; i < cnt; i++) {
                    read_u32(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u8(buf, pos); read_u32(buf, pos);
                }
                break;
            }
            default: {
                // Unknown message type - skip to next message frame
                break;
            }
        }

        // Advance to end of this message frame
        pos = msg_end;
    }

    if (!last_prompt.is_null()) {
        moves.push_back(last_prompt);
    }

    return moves;
}

json ProtocolHandler::serialize_state() {
    auto state = bridge_.get_state();

    json result;
    result["started"] = state.started;
    result["finished"] = state.finished;
    result["winner"] = state.winner;
    result["deck_count"] = {
        {"player1", static_cast<int>(state.deck[0].size())},
        {"player2", static_cast<int>(state.deck[1].size())}
    };
    result["extra_count"] = {
        {"player1", static_cast<int>(state.extra[0].size())},
        {"player2", static_cast<int>(state.extra[1].size())}
    };

    // Use cached messages (don't consume the buffer)
    json events = parse_messages(cached_messages_);
    result["events"] = events;

    // Query field for detailed state
    auto field_data = bridge_.query_field();
    if (!field_data.empty()) {
        result["field_raw"] = serialize_query_data(field_data);
    }

    return result;
}

json ProtocolHandler::serialize_query_data(const std::vector<uint8_t>& data) {
    json result;
    result["size"] = data.size();

    // Convert to hex string for debugging
    std::string hex;
    hex.reserve(data.size() * 2);
    for (uint8_t b : data) {
        static const char hex_chars[] = "0123456789abcdef";
        hex += hex_chars[b >> 4];
        hex += hex_chars[b & 0xF];
    }
    result["raw_hex"] = hex;

    return result;
}
