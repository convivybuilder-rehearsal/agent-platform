import Foundation
import Testing
@testable import IndividuatorDaemonCore

/// `ForwardingRequestMatcher` (build plan slice S5a) carries every test
/// 0092's Handoff names for the forwarding endpoint's matching rule. The
/// allowlist below is the task's own synthetic example, never the real
/// route list (slice S5c).
@Suite struct ForwardingRequestMatcherTests {
    static let allowlist = [
        ForwardingRoute(method: "GET", path: "/v1/widgets/{id}"),
        ForwardingRoute(method: "POST", path: "/v1/widgets/{id}/parts/{rest...}"),
    ]

    private static func match(method: String = "GET", _ target: String) -> Result<ForwardingMatch, ForwardingRefusalReason> {
        ForwardingRequestMatcher.match(method: method, target: Array(target.utf8), allowlist: allowlist)
    }

    @Test(arguments: [
        "/v1/widgets/abc",
        "/v1/widgets/abc?x=1&y=2",
    ])
    func allowedPathIsForwardedByteForByte(target: String) {
        switch Self.match(target) {
        case .success(let m):
            #expect(m.target == Array(target.utf8))
            #expect(m.route.method == "GET")
        case .failure(let reason):
            Issue.record("expected a match, got \(reason)")
        }
    }

    @Test(arguments: [
        ("/v1/widgets/..", ForwardingRefusalReason.dotDotSegment),
        ("/v1/widgets/.", ForwardingRefusalReason.dotSegment),
        ("/v1/widgets//abc", ForwardingRefusalReason.emptyPathSegment),
        ("/v1/widgets/abc/", ForwardingRefusalReason.emptyPathSegment),
        ("/v1/widgets/a\\b", ForwardingRefusalReason.backslashInPath),
        ("/v1/widgets/a%2fb", ForwardingRefusalReason.percentEncodedSlashInPath),
        ("/v1/widgets/a%2Fb", ForwardingRefusalReason.percentEncodedSlashInPath),
        ("/v1/widgets/a%2eb", ForwardingRefusalReason.percentEncodedDotInPath),
        ("/v1/widgets/a%2Eb", ForwardingRefusalReason.percentEncodedDotInPath),
        ("/v1/widgets/a%5cb", ForwardingRefusalReason.percentEncodedBackslashInPath),
        ("/v1/widgets/a%5Cb", ForwardingRefusalReason.percentEncodedBackslashInPath),
        ("/v1/widgets/abc#frag", ForwardingRefusalReason.fragmentPresent),
        ("http://evil.example.com/v1/widgets/abc", ForwardingRefusalReason.targetNotOriginForm),
        ("evil.example.com:443", ForwardingRefusalReason.targetNotOriginForm),
        ("*", ForwardingRefusalReason.targetNotOriginForm),
        ("/v1/unknown/abc", ForwardingRefusalReason.noMatchingRoute),
        ("/v1/widgets/a%20b", ForwardingRefusalReason.parameterCharacterClassViolation),
    ])
    func refusesEachNamedCase(target: String, reason: ForwardingRefusalReason) {
        #expect(Self.match(target) == .failure(reason))
    }

    @Test func refusesCONNECTRegardlessOfItsTarget() {
        #expect(Self.match(method: "CONNECT", "evil.example.com:443") == .failure(.connectMethod))
    }

    @Test func refusesAListedPathCalledWithAnotherMethod() {
        #expect(Self.match(method: "DELETE", "/v1/widgets/abc") == .failure(.methodNotAllowedForPath))
    }

    @Test func trailingMultiSegmentParameterAcceptsSeveralCleanSegments() {
        switch Self.match(method: "POST", "/v1/widgets/abc/parts/p1/p2/p3") {
        case .success(let m):
            #expect(m.target == Array("/v1/widgets/abc/parts/p1/p2/p3".utf8))
            #expect(m.route.method == "POST")
        case .failure(let reason):
            Issue.record("expected a match, got \(reason)")
        }
    }

    @Test func trailingMultiSegmentParameterRefusesWhenAnySegmentBreaksTheRule() {
        #expect(
            Self.match(method: "POST", "/v1/widgets/abc/parts/p1/p2 bad/p3")
                == .failure(.parameterCharacterClassViolation))
    }

    @Test func queryStringIsPassedThroughUnreadAndNeverMatched() {
        // A query string holding bytes the path rule would refuse (here, a
        // '..' token) still matches, because 0092 states the query string
        // is "passed through and never matched" — only the path is read.
        let target = "/v1/widgets/abc?next=../../etc/passwd"
        switch Self.match(target) {
        case .success(let m):
            #expect(m.target == Array(target.utf8))
        case .failure(let reason):
            Issue.record("expected the query string to be passed through unmatched, got \(reason)")
        }
    }
}
