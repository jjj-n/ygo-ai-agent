#include "bridge.h"
#include <fstream>
#include <cstring>
#include <iostream>
#include <random>
#include <sqlite3.h>

DuelBridge::DuelBridge() = default;

DuelBridge::~DuelBridge() {
    destroy_duel();
}

bool DuelBridge::init(const std::string& card_db_path, const std::string& scripts_path) {
    scripts_path_ = scripts_path;
    card_db_.clear();

    // Load card database from CDB (SQLite)
    sqlite3* db = nullptr;
    if (sqlite3_open(card_db_path.c_str(), &db) != SQLITE_OK) {
        std::cerr << "Warning: Cannot open card database: " << card_db_path << std::endl;
        if (db) sqlite3_close(db);
        return false;
    }

    const char* sql = "SELECT id, alias, setcode, type, atk, def, level, race, attribute FROM datas";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        std::cerr << "Warning: Failed to prepare SQL: " << sqlite3_errmsg(db) << std::endl;
        sqlite3_close(db);
        return false;
    }

    int count = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        CardEntry card;
        card.code      = static_cast<uint32_t>(sqlite3_column_int(stmt, 0));
        card.alias     = static_cast<uint32_t>(sqlite3_column_int(stmt, 1));
        card.type      = static_cast<uint32_t>(sqlite3_column_int(stmt, 3));
        card.attribute = static_cast<uint32_t>(sqlite3_column_int(stmt, 8));
        card.race      = static_cast<uint64_t>(sqlite3_column_int64(stmt, 7));
        card.attack    = static_cast<int32_t>(sqlite3_column_int(stmt, 4));
        card.defense   = static_cast<int32_t>(sqlite3_column_int(stmt, 5));

        uint32_t raw_level = static_cast<uint32_t>(sqlite3_column_int(stmt, 6));
        card.level = raw_level & 0xFF;

        // Pendulum scales are stored in upper bits of level
        if (card.type & 0x2000000) { // TYPE_PENDULUM
            card.lscale = (raw_level >> 24) & 0xFF;
            card.rscale = (raw_level >> 16) & 0xFF;
        } else {
            card.lscale = 0;
            card.rscale = 0;
        }

        // Link markers
        if (card.type & 0x400000) { // TYPE_LINK
            card.link_marker = card.defense; // defense field stores link markers for link monsters
        } else {
            card.link_marker = 0;
        }

        // Parse setcodes (stored as 64-bit value, up to 4 setcodes of 16 bits each)
        int64_t raw_setcode = sqlite3_column_int64(stmt, 2);
        card.setcodes.clear();
        for (int i = 0; i < 4; i++) {
            uint16_t sc = (raw_setcode >> (i * 16)) & 0xFFFF;
            if (sc) card.setcodes.push_back(sc);
        }

        card_db_[card.code] = card;
        count++;
    }

    sqlite3_finalize(stmt);
    sqlite3_close(db);

    std::cerr << "Card database loaded: " << card_db_path << " (" << count << " cards)" << std::endl;
    std::cerr << "Scripts path: " << scripts_path << std::endl;
    return true;
}

bool DuelBridge::create_duel(uint64_t seed, uint64_t flags) {
    destroy_duel();

    OCG_DuelOptions options{};
    memset(&options, 0, sizeof(options));

    // Set seed
    if (seed == 0) {
        std::random_device rd;
        std::mt19937_64 gen(rd());
        options.seed[0] = gen();
        options.seed[1] = gen();
        options.seed[2] = gen();
        options.seed[3] = gen();
    } else {
        options.seed[0] = seed;
        options.seed[1] = seed;
        options.seed[2] = seed;
        options.seed[3] = seed;
    }

    options.flags = flags;

    // Default player settings
    options.team1.startingLP = 8000;
    options.team1.startingDrawCount = 5;
    options.team1.drawCountPerTurn = 1;
    options.team2.startingLP = 8000;
    options.team2.startingDrawCount = 5;
    options.team2.drawCountPerTurn = 1;

    // Set callbacks (use static methods with 'this' as payload)
    options.cardReader = reinterpret_cast<OCG_DataReader>(card_reader_callback);
    options.payload1 = this;
    options.scriptReader = reinterpret_cast<OCG_ScriptReader>(script_reader_callback);
    options.payload2 = this;
    options.logHandler = reinterpret_cast<OCG_LogHandler>(log_callback);
    options.payload3 = this;
    options.cardReaderDone = nullptr;
    options.payload4 = nullptr;
    options.enableUnsafeLibraries = 0;

    int result = OCG_CreateDuel(&state_.handle, &options);
    if (result != 0) {
        std::cerr << "OCG_CreateDuel failed with code: " << result << std::endl;
        return false;
    }

    state_.started = false;
    state_.finished = false;
    state_.winner = -1;
    state_.deck[0].clear();
    state_.deck[1].clear();
    state_.extra[0].clear();
    state_.extra[1].clear();

    return true;
}

void DuelBridge::add_card(uint8_t team, uint32_t code, uint32_t loc, uint32_t seq, uint32_t pos) {
    if (!state_.handle) return;

    OCG_NewCardInfo info{};
    info.team = team;
    info.duelist = 0;
    info.code = code;
    info.con = 0;
    info.loc = loc;
    info.seq = seq;
    info.pos = pos;

    OCG_DuelNewCard(state_.handle, &info);

    // Track cards for our reference
    if (loc == LOCATION_DECK) {
        state_.deck[team].push_back(code);
    } else if (loc == LOCATION_EXTRA) {
        state_.extra[team].push_back(code);
    }
}

bool DuelBridge::start_duel() {
    if (!state_.handle) return false;
    OCG_StartDuel(state_.handle);
    state_.started = true;
    return true;
}

int DuelBridge::process() {
    if (!state_.handle) return YGO::DUEL_STATUS_END;

    int status = OCG_DuelProcess(state_.handle);

    if (status == YGO::DUEL_STATUS_END) {
        state_.finished = true;
    }

    return status;
}

std::vector<uint8_t> DuelBridge::get_messages() {
    if (!state_.handle) return {};

    uint32_t length = 0;
    void* data = OCG_DuelGetMessage(state_.handle, &length);
    if (!data || length == 0) return {};

    return std::vector<uint8_t>((uint8_t*)data, (uint8_t*)data + length);
}

void DuelBridge::set_response(const std::vector<uint8_t>& response) {
    if (!state_.handle) return;
    OCG_DuelSetResponse(state_.handle, response.data(), response.size());
}

std::vector<uint8_t> DuelBridge::query_field() {
    if (!state_.handle) return {};

    uint32_t length = 0;
    void* data = OCG_DuelQueryField(state_.handle, &length);
    if (!data || length == 0) return {};

    return std::vector<uint8_t>((uint8_t*)data, (uint8_t*)data + length);
}

std::vector<uint8_t> DuelBridge::query_location(uint8_t team, uint32_t loc, uint32_t flags) {
    if (!state_.handle) return {};

    OCG_QueryInfo info{};
    info.flags = flags;
    info.con = team;
    info.loc = loc;
    info.seq = 0;
    info.overlay_seq = 0;

    uint32_t length = 0;
    void* data = OCG_DuelQueryLocation(state_.handle, &length, &info);
    if (!data || length == 0) return {};

    return std::vector<uint8_t>((uint8_t*)data, (uint8_t*)data + length);
}

uint32_t DuelBridge::query_count(uint8_t team, uint32_t loc) {
    if (!state_.handle) return 0;
    return OCG_DuelQueryCount(state_.handle, team, loc);
}

bool DuelBridge::load_script(const char* buf, uint32_t len, const char* name) {
    if (!state_.handle) return false;
    return OCG_LoadScript(state_.handle, buf, len, name) == 1;
}

void DuelBridge::destroy_duel() {
    if (state_.handle) {
        OCG_DestroyDuel(state_.handle);
        state_.handle = nullptr;
    }
    state_.started = false;
    state_.finished = false;
}

// Static callback implementations
void DuelBridge::card_reader_callback(void* payload, uint32_t code, OCG_CardData* data) {
    auto* self = static_cast<DuelBridge*>(payload);

    // Look up card in database
    auto it = self->card_db_.find(code);
    if (it != self->card_db_.end()) {
        const auto& card = it->second;
        data->code = card.code;
        data->alias = card.alias;
        data->type = card.type;
        data->level = card.level;
        data->attribute = card.attribute;
        data->race = card.race;
        data->attack = card.attack;
        data->defense = card.defense;
        data->lscale = card.lscale;
        data->rscale = card.rscale;
        data->link_marker = card.link_marker;

        // Set setcodes pointer - the setcodes vector in CardEntry stays alive
        // as long as the card_db_ map exists
        if (!card.setcodes.empty()) {
            data->setcodes = const_cast<uint16_t*>(card.setcodes.data());
        } else {
            data->setcodes = nullptr;
        }
    } else {
        // Unknown card - fill with defaults
        memset(data, 0, sizeof(OCG_CardData));
        data->code = code;
    }
}

int DuelBridge::script_reader_callback(void* payload, OCG_Duel duel, const char* name) {
    auto* self = static_cast<DuelBridge*>(payload);

    // Try to load script from file
    std::string path = self->scripts_path_ + "/" + name;
    std::ifstream file(path, std::ios::binary);
    if (!file.is_open()) {
        // Try .lua extension
        path = self->scripts_path_ + "/" + std::string(name) + ".lua";
        file.open(path, std::ios::binary);
        if (!file.is_open()) {
            return 0; // Script not found
        }
    }

    // Read file content
    file.seekg(0, std::ios::end);
    size_t size = file.tellg();
    file.seekg(0, std::ios::beg);

    std::vector<char> buffer(size);
    file.read(buffer.data(), size);
    file.close();

    // Load into engine
    return self->load_script(buffer.data(), static_cast<uint32_t>(size), name) ? 1 : 0;
}

void DuelBridge::log_callback(void* payload, const char* msg, int type) {
    // Log to stderr for debugging
    std::cerr << "[YGOPRO LOG " << type << "] " << msg << std::endl;
}
