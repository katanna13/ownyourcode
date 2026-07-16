// jsdom deliberately leaves window.scrollTo unimplemented. Production code
// uses it for explicit workspace navigation; tests replace it with a no-op
// unless a test needs to observe the call.
window.scrollTo = () => undefined;
