/**
 * Motor determinístico offline do Aponta e Fala (espelho de src/core.py).
 * Garante que a prancha monte frases corretas em PT-BR e sugira o próximo card
 * mesmo quando a internet cair ou o servidor ficar temporariamente inacessível.
 */
(function (global) {
  "use strict";

  const INICIAM = ["eu_quero", "nao_quero", "dor", "terminei", "ajuda", "oi", "tchau", "obrigado"];
  const ACAO_DO_OBJETO = { banheiro: "ir ao banheiro", atividade: "fazer a atividade" };
  const RECIPIENTES = { copo: "um copo", garrafa: "uma garrafa" };
  const CONTEUDOS = new Set(["agua"]);

  function _np(c) {
    return c.np || c.bare || c.label.toLowerCase();
  }

  function _bare(c) {
    if (c.bare) return c.bare;
    if (c.np) return c.np.trim().replace(/^(o|a|os|as|um|uma)\s+/i, "");
    return c.label.toLowerCase();
  }

  function _alvo(c) {
    return ACAO_DO_OBJETO[c.id] || _np(c);
  }

  function _vocativo(c) {
    const b = _bare(c);
    return b ? b.charAt(0).toUpperCase() + b.slice(1) : "";
  }

  function _juntar(partes, conj) {
    if (!partes.length) return "";
    if (partes.length === 1) return partes[0];
    return partes.slice(0, -1).join(", ") + " " + conj + " " + partes[partes.length - 1];
  }

  function _recipiente(rest) {
    if (rest.length === 2) {
      const pairs = [
        [rest[0], rest[1]],
        [rest[1], rest[0]],
      ];
      for (const [rec, con] of pairs) {
        if (RECIPIENTES[rec.id] && CONTEUDOS.has(con.id)) {
          return RECIPIENTES[rec.id] + " de " + _bare(con);
        }
      }
    }
    return null;
  }

  function ordenar(ids, cardsById) {
    const list = (ids || []).filter((i) => Boolean(cardsById[i]));
    if (!list.length) return list;
    let lider = null;
    if (list.includes("ajuda") && (list.includes("eu_quero") || list.includes("nao_quero"))) {
      lider = list.includes("eu_quero") ? "eu_quero" : "nao_quero";
    } else {
      lider = list.find((i) => INICIAM.includes(i)) || null;
    }
    if (lider && list[0] !== lider) {
      list.splice(list.indexOf(lider), 1);
      list.unshift(lider);
    }
    if (list.includes("por_favor") && list[list.length - 1] !== "por_favor") {
      list.splice(list.indexOf("por_favor"), 1);
      list.push("por_favor");
    }
    return list;
  }

  function fraseDor(locCard) {
    const loc = (locCard.loc || "").trim();
    const m = loc.match(/^(na|no|nas|nos)\s+(.*)$/i);
    if (!m) return "Estou com dor " + loc + ".";
    const map = {
      na: ["Minha", "está"],
      no: ["Meu", "está"],
      nas: ["Minhas", "estão"],
      nos: ["Meus", "estão"],
    };
    const [poss, verbo] = map[m[1].toLowerCase()];
    return poss + " " + m[2] + " " + verbo + " doendo.";
  }

  function sentenceWithContext(ids, contexto, cardsById) {
    if (ids.length === 1 && ids[0] === "mais") {
      const objs = (contexto || [])
        .map((i) => cardsById[i])
        .filter((c) => c && c.cat === "objeto");
      if (objs.length) {
        return "Eu quero mais " + _bare(objs[objs.length - 1]) + ".";
      }
    }
    return null;
  }

  function ruleSentence(rawIds, cardsById) {
    const ids = ordenar(rawIds, cardsById);
    const cs = ids.map((i) => cardsById[i]).filter(Boolean);
    if (!cs.length) return null;

    const first = cs[0];
    let rest = cs.slice(1);
    let polite = false;
    if (rest.length && rest[rest.length - 1].id === "por_favor") {
      polite = true;
      rest = rest.slice(0, -1);
    }
    const pf = polite ? ", por favor" : "";

    if (!rest.length && first.spoken) {
      const sp = first.spoken;
      return sp + (sp.endsWith("!") || sp.endsWith("?") ? "" : ".");
    }

    if (first.id === "eu_quero") {
      if (!rest.length) return "Eu quero.";
      if (rest.length === 1) {
        const r = rest[0];
        if (r.id === "mais") return "Eu quero mais" + pf + ".";
        if (r.id === "ajuda") return "Eu quero ajuda" + pf + ".";
        if (r.inf) return "Eu quero " + r.inf + pf + ".";
        if (r.cat === "objeto" || r.cat === "pessoa") return "Eu quero " + _alvo(r) + pf + ".";
      }
      const rec = _recipiente(rest);
      if (rec) return "Eu quero " + rec + pf + ".";
      if (rest.length === 2 && rest[0].id === "mais" && rest[1].cat === "objeto") {
        return "Eu quero mais " + _bare(rest[1]) + pf + ".";
      }
      if (rest.length === 2 && rest[1].id === "mais" && rest[0].cat === "objeto") {
        return "Eu quero mais " + _bare(rest[0]) + pf + ".";
      }
      return null;
    }

    if (first.id === "nao_quero") {
      const rec = _recipiente(rest);
      if (rec) return "Não quero " + rec + ".";
      if (rest.length === 1) {
        const r = rest[0];
        if (r.id === "ajuda") return "Não quero ajuda" + pf + ".";
        if (r.inf) return "Não quero " + r.inf + ".";
        if (r.cat === "objeto" || r.cat === "pessoa") return "Não quero " + _alvo(r) + ".";
      }
      return null;
    }

    if (
      first.id === "dor" &&
      rest.length &&
      rest.every((r) => Boolean(r.loc) || r.cat === "pessoa") &&
      rest.some((r) => Boolean(r.loc))
    ) {
      const locs = rest.filter((r) => Boolean(r.loc));
      const pess = rest.filter((r) => r.cat === "pessoa");
      const voc = pess.length ? _vocativo(pess[0]) + ", " : "";
      let f;
      if (locs.length === 1) {
        f = fraseDor(locs[0]);
      } else {
        const possMap = { na: "minha", no: "meu", nas: "minhas", nos: "meus" };
        const partes = locs.map((l) => {
          const m = l.loc.trim().match(/^(na|no|nas|nos)\s+(.*)$/i);
          return m ? possMap[m[1].toLowerCase()] + " " + m[2] : l.loc;
        });
        const j = _juntar(partes, "e");
        f = j.charAt(0).toUpperCase() + j.slice(1) + " estão doendo.";
      }
      const out = voc ? voc + f.charAt(0).toLowerCase() + f.slice(1) : f;
      return out.replace("..", ".");
    }

    if (first.id === "terminei" && rest.length === 1 && rest[0].cat === "objeto") {
      return "Terminei " + _np(rest[0]) + ".";
    }
    if (first.id === "ajuda" && rest.length === 1 && rest[0].id === "banheiro") {
      return "Preciso de ajuda para ir ao banheiro.";
    }
    if (first.id === "ajuda" && rest.length === 1 && rest[0].cat === "objeto") {
      return "Preciso de ajuda com " + _np(rest[0]) + ".";
    }
    if (first.id === "ajuda" && rest.length === 1 && rest[0].cat === "pessoa") {
      return _vocativo(rest[0]) + ", preciso de ajuda.";
    }

    if (cs.length === 2 && new Set([cs[0].cat, cs[1].cat]).size === 2 && cs.some((c) => c.cat === "sentir") && cs.some((c) => c.cat === "pessoa")) {
      const sen = cs[0].cat === "sentir" ? cs[0] : cs[1];
      const pes = sen === cs[0] ? cs[1] : cs[0];
      if (sen.spoken && !sen.loc) {
        return _vocativo(pes) + ", " + sen.spoken.charAt(0).toLowerCase() + sen.spoken.slice(1) + ".";
      }
    }

    if (["oi", "tchau", "obrigado"].includes(first.id) && rest.length === 1 && rest[0].cat === "pessoa") {
      const saud = { oi: "Oi", tchau: "Tchau", obrigado: "Obrigado" }[first.id];
      return saud + ", " + _bare(rest[0]) + "!";
    }

    if (first.id === "terminei" && rest.length === 1 && rest[0].cat === "pessoa") {
      return _vocativo(rest[0]) + ", terminei.";
    }

    const nucleo = [first].concat(rest);
    if (nucleo.length === 2) {
      const idsSet = new Set(nucleo.map((c) => c.id));
      const obj = nucleo.find((c) => c.cat === "objeto");
      if (obj && idsSet.has("mais")) return "Mais " + _bare(obj) + pf + ".";
      if (obj && idsSet.has("acabou")) return "Acabou " + _np(obj) + pf + ".";
    }

    return null;
  }

  function listaSentence(rawIds, cardsById) {
    let ids = ordenar(rawIds, cardsById);
    const cs = ids.map((i) => cardsById[i]).filter(Boolean);
    if (
      cs.length >= 2 &&
      cs.every((x) => x.cat === "sentir" && !x.loc && x.id !== "dor" && (x.spoken || "").startsWith("Estou "))
    ) {
      return "Estou " + _juntar(cs.map((x) => x.spoken.slice(6)), "e") + ".";
    }
    if (ids.length < 3 || (ids[0] !== "eu_quero" && ids[0] !== "nao_quero")) return null;
    let pf = "";
    if (ids[ids.length - 1] === "por_favor") {
      ids = ids.slice(0, -1);
      pf = ", por favor";
    }
    const itens = ids.slice(1).map((i) => cardsById[i]).filter(Boolean);
    if (itens.length < 2 || !itens.every((x) => x.cat === "objeto" || x.cat === "pessoa" || Boolean(x.inf))) {
      return null;
    }
    const partes = itens.map((x) => (x.inf && x.cat !== "objeto" ? x.inf : _alvo(x)));
    if (ids[0] === "eu_quero") return "Eu quero " + _juntar(partes, "e") + pf + ".";
    return "Não quero " + _juntar(partes, "nem") + ".";
  }

  function fallbackSentence(ids, cardsById) {
    const cs = (ids || []).map((i) => cardsById[i]).filter(Boolean);
    if (!cs.length) return "";
    const pess = cs.filter((c) => c.cat === "pessoa" && cs.length > 1);
    const resto = cs.filter((c) => !pess.includes(c) && c.id !== "por_favor");
    const pf = cs.some((c) => c.id === "por_favor") ? ", por favor" : "";
    const voc = pess.length ? _vocativo(pess[0]) + ", " : "";

    if (resto.some((c) => c.id === "dor")) {
      const locs = resto.filter((c) => Boolean(c.loc));
      if (locs.length) {
        const f = fraseDor(locs[0]);
        return voc ? voc + f.charAt(0).toLowerCase() + f.slice(1) : f;
      }
    }

    const partes = resto.map((c) => {
      const sp = c.spoken || "";
      if (c.cat === "sentir" && sp.startsWith("Estou ")) return sp.slice(6);
      return c.label.toLowerCase();
    });
    let txt;
    if (resto.length && resto.every((c) => c.cat === "sentir" && (c.spoken || "").startsWith("Estou "))) {
      txt = "estou " + _juntar(partes, "e");
    } else {
      txt = _juntar(partes, "e");
    }
    const f = voc ? voc + txt : txt;
    return f.charAt(0).toUpperCase() + f.slice(1) + pf + ".";
  }

  function falarOffline(rawSeq, contexto, cardsById) {
    const ordem = ordenar(rawSeq, cardsById);
    let frase = sentenceWithContext(ordem, contexto, cardsById) || ruleSentence(ordem, cardsById);
    let fonte = "offline-regra";
    if (!frase) {
      frase = listaSentence(ordem, cardsById);
      if (frase) fonte = "offline-lista";
    }
    if (!frase) {
      frase = fallbackSentence(ordem, cardsById);
      fonte = "offline-fallback";
    }
    return { frase, ordem, fonte };
  }

  function sugerirOffline(rotina, seq, ngram, k) {
    if (!ngram) return [];
    const prev = seq && seq.length ? seq[seq.length - 1] : "<s>";
    const key = rotina + "|" + prev;
    return (ngram[key] || []).slice(0, k || 4);
  }

  global.ApontaOffline = {
    ordenar,
    falarOffline,
    sugerirOffline,
  };
})(window);
