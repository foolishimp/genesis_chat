"use strict";

module.exports = {
    // Public mode — no login required, open in browser and go
    public: true,
    port: 9000,
    host: undefined,

    // Pre-connect to our miniircd instance
    defaults: {
        name: "GenesisNet",
        host: "irc",
        port: 6667,
        tls: false,
        rejectUnauthorized: false,
        nick: "human",
        username: "human",
        realname: "Human Operator",
        join: "#genesis",
    },
};
