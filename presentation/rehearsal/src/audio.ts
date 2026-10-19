export function wavHeader(bytes: number, rate = 16_000) {
  const header = new ArrayBuffer(44);
  const view = new DataView(header);
  function text(offset: number, value: string) {
    for (let index = 0; index < value.length; index++) view.setUint8(offset + index, value.charCodeAt(index));
  }
  text(0, "RIFF");
  view.setUint32(4, bytes + 36, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, bytes, true);
  return header;
}

export function encodeWav(samples: Float32Array, rate = 16_000) {
  const pcm = new ArrayBuffer(samples.length * 2);
  const view = new DataView(pcm);
  for (let index = 0; index < samples.length; index++) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(index * 2, Math.round(sample * (sample < 0 ? 32768 : 32767)), true);
  }
  return new Blob([wavHeader(pcm.byteLength, rate), pcm], { type: "audio/wav" });
}

export function combineWavs(chunks: Blob[]) {
  const size = chunks.reduce((sum, chunk) => sum + chunk.size - 44, 0);
  return new Blob([wavHeader(size), ...chunks.map(chunk => chunk.slice(44))], { type: "audio/wav" });
}
