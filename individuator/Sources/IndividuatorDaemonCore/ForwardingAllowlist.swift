import Foundation

/// The forwarding endpoint's fixed, in-code allowlist (0092: "It forwards a
/// fixed set of routes, and nothing else... It is a list in the
/// Individuator's code, so adding a route is a reviewed code change.").
///
/// Empty in this slice (E12·2 S5b): the real route list — the Library
/// protocol routes the host's clients call, and the Bosun's run-register
/// and session-view paths — is slice S5c's, built from those clients' own
/// call sites. An empty allowlist means every request the forwarding
/// socket accepts is refused as `noMatchingRoute`, which is this slice's
/// correct, safe default: the mechanism works end to end, and nothing is
/// actually reachable through it yet.
public enum ForwardingAllowlist {
    public static let entries: [ForwardingRouteEntry] = []
}
