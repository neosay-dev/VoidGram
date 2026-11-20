// VoidGram for Android: the host object the iOS plugin prelude expects (root.__ayuHost), built on
// a native object that only passes strings and numbers (QuickJS). Functions stay on this side:
// hooks, event listeners and timers are kept here and Java calls back through __ayuDispatch*.
(function (root) {
    'use strict';
    const N = root.__native;
    delete root.__native;
    const hooks = {};
    const events = {};
    const timers = {};
    let nextTimer = 1;
    const parse = (value) => {
        if (value === null || value === undefined) return undefined;
        try { return JSON.parse(value); } catch (e) { return undefined; }
    };
    const report = (where, error) => {
        try { N.log('error', where + ': ' + (error && error.stack ? error.stack : String(error))); } catch (e) {}
    };
    root.__ayuHost = {
        pluginId: N.pluginId(),
        call: function (op, args) {
            const answer = parse(N.call(String(op), JSON.stringify(args === undefined ? {} : args)));
            return answer === undefined ? false : answer;
        },
        log: (level, message) => N.log(String(level), String(message)),
        toast: (message) => N.toast(String(message)),
        on: function (event, fn) {
            if (typeof fn !== 'function') return;
            (events[event] = events[event] || []).push(fn);
        },
        hook: function (point, mode, fn) {
            if (typeof fn !== 'function') return false;
            const key = String(point) + '|' + String(mode);
            (hooks[key] = hooks[key] || []).push(fn);
            N.hookRegistered(String(point), String(mode));
            return true;
        },
        feature: (name, enabled) => N.call('feature', JSON.stringify({ name: String(name), enabled: !!enabled })) === 'true',
        setTimer: function (fn, ms, repeats) {
            if (typeof fn !== 'function') return 0;
            const id = nextTimer++;
            timers[id] = { fn: fn, repeats: !!repeats };
            N.setTimer(id, Math.max(0, Number(ms) || 0), !!repeats);
            return id;
        },
        clearTimer: function (id) {
            delete timers[id];
            N.clearTimer(Number(id) || 0);
        },
        storageGet: function (key) {
            const value = N.storageGet(String(key));
            return value === null ? undefined : value;
        },
        storageSet: (key, value) => N.storageSet(String(key), value === null || value === undefined ? null : String(value)),
        settingGet: (key) => parse(N.settingGet(String(key))),
        settingsDeclare: (items) => N.settingsDeclare(JSON.stringify(items || [])),
        playerControl: (action) => N.call('player.control', JSON.stringify({ action: String(action) })) === 'true',
        playerState: () => parse(N.call('player.state', '{}')) || {},
        setObject: () => false,
        replace: () => false
    };
    // Java → JS: a hook. Returns the replacement text, '\u0000' to cancel, or null to keep it.
    root.__ayuDispatchHook = function (point, mode, value, contextJson) {
        const list = hooks[point + '|' + mode];
        if (!list) return null;
        const context = parse(contextJson) || {};
        let current = value;
        let changed = false;
        for (let i = 0; i < list.length; i++) {
            try {
                const result = list[i](current, context);
                if (result === '\u0000') return '\u0000';
                if (typeof result === 'string') { current = result; changed = true; }
            } catch (error) {
                report('hook ' + point, error);
            }
        }
        return changed ? current : null;
    };
    root.__ayuDispatchEvent = function (event, payloadJson) {
        const list = events[event];
        if (!list) return;
        const payload = parse(payloadJson);
        for (let i = 0; i < list.length; i++) {
            try { list[i](payload); } catch (error) { report('event ' + event, error); }
        }
    };
    root.__ayuDispatchTimer = function (id) {
        const timer = timers[id];
        if (!timer) return;
        if (!timer.repeats) delete timers[id];
        try { timer.fn(); } catch (error) { report('timer', error); }
    };
})(globalThis);
