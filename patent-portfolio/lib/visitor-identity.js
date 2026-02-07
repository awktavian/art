/**
 * Visitor Identity & Journey Export
 * ==================================
 *
 * Ephemeral DID per session, track visited patents, "export my journey" as Agent Data Pod.
 * h(x) ≥ 0 always
 */

const AGENT_VOCAB = 'https://awkronos.github.io/web/vocab#';
const DCT = 'http://purl.org/dc/terms/';
const XSD = 'http://www.w3.org/2001/XMLSchema#';

function randomId() {
    const u = typeof crypto !== 'undefined' && crypto.getRandomValues
        ? crypto.getRandomValues(new Uint8Array(16))
        : Array.from({ length: 16 }, () => Math.floor(Math.random() * 256));
    return Array.from(u, b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Generate an ephemeral DID for this session (did:key-style placeholder; not a real did:key)
 */
function createEphemeralDid() {
    const hex = randomId() + randomId();
    return `did:ephemeral:museum-${hex}`;
}

function escapeTurtle(s) {
    if (s == null) return '""';
    return '"' + String(s)
        .replace(/\\/g, '\\\\')
        .replace(/"/g, '\\"')
        .replace(/\n/g, '\\n')
        .replace(/\r/g, '\\r') + '"';
}

/**
 * Visitor identity + journey tracker for Agent Data Pod export
 */
export class VisitorIdentity {
    constructor(options = {}) {
        this.did = options.did || createEphemeralDid();
        this.visitedPatents = []; // { patentId, at: ISO date string }
        this.startedAt = new Date().toISOString();
        this._solidPodUrl = options.solidPodUrl || null;
    }

    /**
     * Record a patent visit
     * @param {string} patentId
     */
    recordVisit(patentId) {
        if (!patentId) return;
        const at = new Date().toISOString();
        const existing = this.visitedPatents.find(p => p.patentId === patentId);
        if (existing) existing.at = at;
        else this.visitedPatents.push({ patentId, at });
    }

    /**
     * Get visited patent IDs (e.g. for journey tracker UI)
     */
    getVisitedIds() {
        return this.visitedPatents.map(p => p.patentId);
    }

    /**
     * Export "my journey" as RDF/Turtle (Agent Data Pod style).
     * Each visit is an agent:MemoryEpisode with content = "Visited patent {id} at {time}".
     * @param {object[]} [patentLookup] - Optional list of patent objects to enrich episode content
     * @returns {string}
     */
    exportJourneyAsRDF(patentLookup = []) {
        const base = typeof window !== 'undefined' && window.location?.origin
            ? window.location.origin
            : 'https://patent-museum.example';
        const journeyUri = `${base}/journey/${encodeURIComponent(this.did)}`;
        const lines = [
            `@prefix agent: <${AGENT_VOCAB}> .`,
            `@prefix dct: <${DCT}> .`,
            `@prefix xsd: <${XSD}> .`,
            '',
            `<${journeyUri}>`,
            `    a agent:AIAgent ;`,
            `    dct:identifier ${escapeTurtle(this.did)} ;`,
            `    dct:created "${this.startedAt}"^^xsd:dateTime .`,
            ''
        ];
        this.visitedPatents.forEach((visit, i) => {
            const patent = patentLookup.find(p => p.id === visit.patentId);
            const content = patent
                ? `Visited: ${patent.name} (${visit.patentId}) at ${visit.at}`
                : `Visited patent ${visit.patentId} at ${visit.at}`;
            const episodeUri = `${journeyUri}#episode-${i}`;
            lines.push(
                `<${episodeUri}>`,
                `    a agent:MemoryEpisode ;`,
                `    agent:content ${escapeTurtle(content)} ;`,
                `    dct:created "${visit.at}"^^xsd:dateTime ;`,
                `    agent:memoryType "episodic" ;`,
                `    agent:tag ${escapeTurtle(visit.patentId)} .`,
                ''
            );
        });
        return lines.join('\n');
    }

    /**
     * Trigger download of journey as .ttl file
     * @param {object[]} [patentLookup]
     */
    downloadJourney(patentLookup = []) {
        const ttl = this.exportJourneyAsRDF(patentLookup);
        const blob = new Blob([ttl], { type: 'text/turtle' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `museum-journey-${this.did.replace(/:/g, '-')}.ttl`;
        a.click();
        URL.revokeObjectURL(url);
    }

    /** Optional: set Solid Pod URL for future write-back */
    setSolidPodUrl(url) {
        this._solidPodUrl = url;
    }
}

const defaultInstance = { _instance: null };

/**
 * Get or create singleton visitor identity for this session
 * @returns {VisitorIdentity}
 */
export function getVisitorIdentity() {
    if (!defaultInstance._instance) {
        defaultInstance._instance = new VisitorIdentity();
    }
    return defaultInstance._instance;
}

export default VisitorIdentity;
