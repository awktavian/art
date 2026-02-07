/**
 * Agent Data Pod — RDF serialization of patent metadata
 * ======================================================
 *
 * Serializes patent metadata as RDF/Turtle per Awkronos Agent Data Pod spec.
 * Namespace: https://awkronos.github.io/web/vocab#
 * Each patent as agent:MemoryEpisode with content, created, importance, memoryType, tag.
 *
 * h(x) ≥ 0 always
 */

const AGENT_VOCAB = 'https://awkronos.github.io/web/vocab#';
const DCT = 'http://purl.org/dc/terms/';
const XSD = 'http://www.w3.org/2001/XMLSchema#';

/**
 * Map novelty 1–5 to importance 0.2–1.0
 * @param {number} novelty
 * @returns {number}
 */
function importanceFromNovelty(novelty) {
    if (typeof novelty !== 'number' || novelty < 1) return 0.2;
    if (novelty > 5) return 1;
    return 0.2 + (novelty - 1) * (0.8 / 4);
}

/**
 * Escape string for Turtle (double quotes, backslash, newline)
 * @param {string} s
 * @returns {string}
 */
function escapeTurtle(s) {
    if (s == null) return '""';
    return '"' + String(s)
        .replace(/\\/g, '\\\\')
        .replace(/"/g, '\\"')
        .replace(/\n/g, '\\n')
        .replace(/\r/g, '\\r') + '"';
}

/**
 * Serialize a single patent as agent:MemoryEpisode in Turtle lines
 * @param {object} patent - { id, name, description, invented, novelty, category, categoryName, colony, priority }
 * @param {string} baseUri - Base URI for episode URIs (e.g. https://example.com/museum/patents/)
 * @returns {string[]}
 */
function patentToTurtleLines(patent, baseUri) {
    const episodeUri = (baseUri.endsWith('/') ? baseUri : baseUri + '/') + encodeURIComponent(patent.id);
    const lines = [
        `<${episodeUri}>`,
        `    a <${AGENT_VOCAB}MemoryEpisode> ;`,
        `    <${AGENT_VOCAB}content> ${escapeTurtle(patent.description || patent.name)} ;`,
        `    <${DCT}created> "${patent.invented || ''}"^^<${XSD}date> ;`,
        `    <${AGENT_VOCAB}importance> ${importanceFromNovelty(patent.novelty).toFixed(2)} ;`,
        `    <${AGENT_VOCAB}memoryType> "semantic" ;`,
        `    <${AGENT_VOCAB}tag> ${escapeTurtle(patent.category)} , ${escapeTurtle(patent.colony)} , ${escapeTurtle(patent.priority)} .`
    ];
    return lines;
}

/**
 * Serialize all patents to RDF/Turtle
 * @param {object[]} patents - Array of patent objects
 * @param {string} [baseUri] - Base URI for episode resources (default: museum origin + /patents/)
 * @returns {string}
 */
export function serializePatentsAsRDF(patents, baseUri) {
    const base = baseUri || (typeof window !== 'undefined' && window.location?.origin
        ? window.location.origin + '/patents/'
        : 'https://patent-museum.example/patents/');
    
    const lines = [
        `@prefix agent: <${AGENT_VOCAB}> .`,
        `@prefix dct: <${DCT}> .`,
        `@prefix xsd: <${XSD}> .`,
        ''
    ];
    
    patents.forEach((patent) => {
        lines.push(...patentToTurtleLines(patent, base));
        lines.push('');
    });
    
    return lines.join('\n');
}

/**
 * Create agent-pod serializer with optional patent list (e.g. from PATENTS in info-panel)
 * @param {object[]} [patentList] - Optional patent list; if omitted, pass patents to serialize()
 */
export function createAgentPodSerializer(patentList = null) {
    const list = patentList || [];
    return {
        serialize(baseUri, patents = list) {
            return serializePatentsAsRDF(patents.length ? patents : list, baseUri);
        }
    };
}

export default serializePatentsAsRDF;
