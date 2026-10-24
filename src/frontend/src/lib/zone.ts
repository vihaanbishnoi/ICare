/** Which fall positions a danger-zone map draws. */
export type Layer = 'onset' | 'landing' | 'both';

/** RGB triples: red where a fall began, orange where the person landed. */
export const ONSET_RGB = '220, 38, 38';
export const LANDING_RGB = '245, 158, 11';
