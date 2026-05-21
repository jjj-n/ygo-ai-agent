#include "bridge.h"
#include "protocol.h"
#include <nlohmann/json.hpp>
#include <iostream>
#include <string>

using json = nlohmann::json;

int main(int argc, char* argv[]) {
    // Configuration from environment or command line
    std::string card_db_path = "cards.cdb";
    std::string scripts_path = "scripts";

    if (argc >= 2) card_db_path = argv[1];
    if (argc >= 3) scripts_path = argv[2];

    // Initialize bridge
    DuelBridge bridge;
    if (!bridge.init(card_db_path, scripts_path)) {
        std::cerr << "Warning: Failed to load card database. Continuing with empty DB." << std::endl;
    }

    ProtocolHandler protocol(bridge);

    // Main loop: read JSON from stdin, write responses to stdout
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;

        try {
            json cmd = json::parse(line);
            json response = protocol.handle_command(cmd);

            // Write response to stdout
            std::cout << response.dump() << std::endl;
            std::cout.flush();

        } catch (const json::parse_error& e) {
            json error = {{"ok", false}, {"error", "parse_error"}, {"reason", e.what()}};
            std::cout << error.dump() << std::endl;
            std::cout.flush();
        } catch (const std::exception& e) {
            json error = {{"ok", false}, {"error", "internal_error"}, {"reason", e.what()}};
            std::cout << error.dump() << std::endl;
            std::cout.flush();
        }
    }

    return 0;
}
