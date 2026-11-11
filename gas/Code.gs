// Chemin exact : gas/Code.gs [MODIFIÉ]
/**
 * Google Apps Script API for the Offres and refresh-log sheets.
 *
 * RÈGLES DE GESTION
 *
 * Configuration — doGet()
 * - L'action get_config exige API_SECRET.
 * - La réponse fournit les URL déjà présentes dans Offres, les URL de Sources
 *   et les critères de Cible véhicules.
 * - Une configuration de critères absente ou incomplète provoque une erreur;
 *   le GAS ne remplace pas les valeurs manquantes par des valeurs par défaut.
 *
 * Réception et dédoublonnage — doPost()
 * - Le POST exige une signature HMAC valide, un horodatage à moins de 5 minutes
 *   de l'horloge du GAS et un request_id UUID non réutilisé pendant 10 minutes
 *   (durée de conservation de la clé anti-rejeu en cache).
 * - Chaque annonce doit contenir exactement 14 colonnes et une URL.
 * - Une URL déjà présente dans Offres, ou répétée dans le même lot, n'est pas
 *   insérée une seconde fois.
 * - Le GAS recalcule toujours CONFORME à partir des critères et des faits reçus;
 *   la valeur de conformité transmise dans l'annonce n'est pas retenue.
 *
 * Conformité — evaluateVehicleConformity_()
 * - Chaque annonce est comparée à chaque ligne renseignée de Cible véhicules.
 * - L'annonce est CONFORME si elle satisfait tous les critères d'au moins une
 *   ligne.
 * - Si aucune ligne ne permet de conclure et qu'au moins une contient des faits
 *   manquants, le résultat est À VÉRIFIER; sinon, il est NON CONFORME.
 * - Prix et kilométrage doivent être inférieurs ou égaux à leur maximum;
 *   l'année doit être supérieure ou égale à son minimum; la distance doit être
 *   inférieure ou égale à son maximum. Les bornes sont inclusives.
 * - La distance est une donnée reçue dans la colonne Dist.; ce GAS ne calcule
 *   pas l'itinéraire en voiture.
 * - Une exclusion trouvée dans le titre, la description ou exclusion_text rend
 *   l'annonce NON CONFORME. La recherche ignore casse et accents et s'effectue
 *   sur les limites de mots.
 * - Marque et modèle peuvent être déduits du titre si les faits reçus ne les
 *   précisent pas. Une donnée requise encore absente, notamment énergie, places
 *   ou distance, conduit à À VÉRIFIER.
 *
 * Écriture et journalisation — doPost()
 * - Le GAS verrouille l'écriture, insère les nouvelles annonces en haut de
 *   Offres et le bilan de l'exécution en haut de Journal.
 * - Les textes pouvant être interprétés comme des formules Sheets sont
 *   neutralisés avant insertion.
 * - testEcriture() écrit réellement des lignes de test dans Offres et Journal;
 *   ne l'exécuter que si ces écritures sont souhaitées.
 */
const API_SECRET = PropertiesService.getScriptProperties().getProperty("API_SECRET");
const HMAC_SECRET = PropertiesService.getScriptProperties().getProperty("HMAC_SECRET");
const TARGET_SHEET_NAME = "Offres";
const REFRESH_LOG_SHEET_NAME = "Journal";
const CRITERIA_SHEET_NAME = "Cible véhicules";
const CONFORMITY_STATUS = {
  CONFORMING: "CONFORME",
  NON_CONFORMING: "NON CONFORME",
  NEEDS_REVIEW: "À VÉRIFIER"
};
const VEHICLE_COLUMNS = [
  "Date", "Title", "Price", "Mileage", "Year", "City", "Dist.", "Notebook",
  "CONFORME", "Risk", "Comment", "Seller", "Source", "URL"
];
const REFRESH_LOG_COLUMNS = ["Date", "Début", "Fin", "Durée (mn)", "Statut / Total"];

// Ligne de référence fournie pour test, dans l'ordre des 14 colonnes :
// 29/09/2026 | ToyTest yaya | 9999 | 99999 | 0 | MaVille | 999 | NC |
// CONFORME | AlerteRisque | Commentaire | TESTAUTO | SOURCETEST |
// https://www.testsite.fr/ad/voitures/3206865999
// Seconde ligne de test identique, marquée NON CONFORME, avec URL distincte.
//
// Exemple de ligne pour "Journal" :
// 29/10/2026 | 18:52 | 18:52 | 0 |
// Terminée - 1 annonce conforme ajoutée, 1 annonce non conforme ajoutée / 2 au total.

function doGet(e) {
  const params = e && e.parameter ? e.parameter : {};
  if (!API_SECRET || !slowEquals_(params.secret || "", API_SECRET)) {
    return createJsonResponse({ status: "error", message: "Accès non autorisé." });
  }
  if (params.action !== "get_config") {
    return createJsonResponse({ status: "error", message: "Action inconnue." });
  }

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const offersSheet = ss.getSheetByName(TARGET_SHEET_NAME);
  const keys = [];
  if (offersSheet && offersSheet.getLastRow() > 1) {
    const urlColumn = VEHICLE_COLUMNS.indexOf("URL") + 1;
    const values = offersSheet
      .getRange(2, urlColumn, offersSheet.getLastRow() - 1, 1)
      .getDisplayValues();
    values.forEach(function(row) {
      const url = String(row[0] || "");
      if (url) {
        keys.push(url);
      }
    });
  }

  const sourcesSheet = ss.getSheetByName("Sources");
  const targets = [];
  if (sourcesSheet && sourcesSheet.getLastRow() > 1) {
    const values = sourcesSheet.getRange(2, 2, sourcesSheet.getLastRow() - 1, 1).getValues();
    values.forEach(function(row) {
      const target = String(row[0] || "");
      if (target) {
        targets.push(target);
      }
    });
  }

  const criteria = readVehicleCriteria_(ss);
  return createJsonResponse({
    status: "success",
    keys: keys,
    targets: targets,
    criteria: criteria
  });
}

function testEcriture() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) {
    throw new Error("Impossible d'obtenir le verrou du Google Sheet.");
  }

  const startedAt = new Date();
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const offersSheet = ss.getSheetByName(TARGET_SHEET_NAME);
    const logSheet = ss.getSheetByName(REFRESH_LOG_SHEET_NAME);
    if (!offersSheet || !logSheet) {
      const missingSheets = [];
      if (!offersSheet) {
        missingSheets.push(TARGET_SHEET_NAME);
      }
      if (!logSheet) {
        missingSheets.push(REFRESH_LOG_SHEET_NAME);
      }
      throw new Error("Onglet(s) requis manquant(s) : " + missingSheets.join(", "));
    }
    validateSheetColumns_(offersSheet, TARGET_SHEET_NAME, VEHICLE_COLUMNS.length);
    validateSheetColumns_(logSheet, REFRESH_LOG_SHEET_NAME, REFRESH_LOG_COLUMNS.length);

    const testId = Utilities.getUuid();
    const row = [
      startedAt,
      "ToyTest yaya",
      9999,
      99999,
      0,
      "MaVille",
      999,
      "NC",
      "CONFORME",
      "AlerteRisque",
      "Test manuel testEcriture()",
      "TESTAUTO",
      "SOURCETEST",
      "https://www.testsite.fr/ad/testecriture-" + testId
    ];
    const nonConformingRow = row.slice();
    nonConformingRow[8] = "NON CONFORME";
    nonConformingRow[13] += "?non-conforme";

    insertRowsAtTop_(offersSheet, [row, nonConformingRow].map(function(testRow) {
      return testRow.map(sanitizeCell_);
    }));
    if (logSheet.getLastRow() >= 2) {
      logSheet.insertRowsBefore(2, 1);
    }
    const testLogRow = logSheet.getRange(2, 1, 1, REFRESH_LOG_COLUMNS.length);
    logSheet.getRange(2, 2, 1, 2).setNumberFormat("@");
    testLogRow.setValues([[
      "99/99/9999",
      "99:99",
      "99:99",
      9,
      "Test manuel testEcriture() : 1 annonce conforme et 1 annonce non conforme."
    ]]);

    const result = "Accès au Google Sheet confirmé; deux annonces de test (une conforme, une non conforme) et une ligne de journal ont été ajoutées.";
    Logger.log(result + " URL: " + row[13]);
    return result;
  } finally {
    lock.releaseLock();
  }
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  let lockAcquired = false;
  let startedAt;
  try {
    if (!HMAC_SECRET || !e || !e.postData || !e.postData.contents) {
      return createJsonResponse({ status: "error", message: "Requête ou configuration invalide." });
    }

    const rawBody = e.postData.contents;
    const signature = e.parameter ? e.parameter.signature || "" : "";
    if (!verifyHmacSignature_(HMAC_SECRET, rawBody, signature)) {
      return createJsonResponse({ status: "error", message: "Signature HMAC invalide." });
    }

    const payload = JSON.parse(rawBody);
    if (!Number.isInteger(payload.timestamp) ||
        Math.abs(Math.floor(Date.now() / 1000) - payload.timestamp) > 300 ||
        typeof payload.request_id !== "string" ||
        !/^[a-f0-9-]{36}$/i.test(payload.request_id)) {
      return createJsonResponse({ status: "error", message: "Horodatage ou identifiant de requête invalide/expiré." });
    }

    if (!Array.isArray(payload.offers)) {
      return createJsonResponse({ status: "error", message: "Le champ offers doit être un tableau." });
    }

    const logData = payload.log && typeof payload.log === "object" ? payload.log : {};
    const totalCount = logData.total_count === undefined ? payload.offers.length : logData.total_count;
    if (!Number.isInteger(totalCount) || totalCount < payload.offers.length) {
      return createJsonResponse({ status: "error", message: "log.total_count doit être un entier au moins égal au nombre d'offres reçues." });
    }

    if (!lock.tryLock(10000)) {
      return createJsonResponse({ status: "error", message: "Serveur occupé, réessayez plus tard." });
    }
    lockAcquired = true;
    startedAt = new Date();

    const cache = CacheService.getScriptCache();
    const replayKey = "signed_post_" + payload.request_id;
    if (cache.get(replayKey)) {
      return createJsonResponse({ status: "error", message: "Requête déjà traitée." });
    }
    cache.put(replayKey, "1", 600);

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const offersSheet = ss.getSheetByName(TARGET_SHEET_NAME);
    const logSheet = ss.getSheetByName(REFRESH_LOG_SHEET_NAME);
    if (!offersSheet || !logSheet) {
      const missingSheets = [];
      if (!offersSheet) {
        missingSheets.push(TARGET_SHEET_NAME);
      }
      if (!logSheet) {
        missingSheets.push(REFRESH_LOG_SHEET_NAME);
      }
      throw new Error("Onglet(s) requis manquant(s) : " + missingSheets.join(", "));
    }
    validateSheetColumns_(offersSheet, TARGET_SHEET_NAME, VEHICLE_COLUMNS.length);
    validateSheetColumns_(logSheet, REFRESH_LOG_SHEET_NAME, REFRESH_LOG_COLUMNS.length);
    const criteria = readVehicleCriteria_(ss);
    const urlColumn = VEHICLE_COLUMNS.indexOf("URL");
    const conformityColumn = VEHICLE_COLUMNS.indexOf("CONFORME");
    const commentColumn = VEHICLE_COLUMNS.indexOf("Comment");
    const existingUrls = new Set();
    if (offersSheet.getLastRow() > 1) {
      offersSheet
        .getRange(2, urlColumn + 1, offersSheet.getLastRow() - 1, 1)
        .getDisplayValues()
        .forEach(function(row) {
          if (row[0]) {
            existingUrls.add(String(row[0]));
          }
        });
    }

    const rowsToAdd = [];
    payload.offers.forEach(function(offer) {
      if (!Array.isArray(offer) || offer.length !== VEHICLE_COLUMNS.length) {
        throw new Error("Chaque annonce doit contenir exactement 14 colonnes.");
      }
      const url = String(offer[urlColumn] || "");
      if (!url) {
        throw new Error("Chaque annonce doit avoir une URL.");
      }
      if (!existingUrls.has(url)) {
        const row = offer.slice();
        const facts = payload.vehicle_facts &&
          Object.prototype.hasOwnProperty.call(payload.vehicle_facts, url)
          ? payload.vehicle_facts[url]
          : {};
        const evaluation = evaluateVehicleConformity_(row, facts, criteria);
        row[conformityColumn] = evaluation.status;
        row[commentColumn] = appendConformityReasons_(row[commentColumn], evaluation.reasons);
        rowsToAdd.push(row.map(sanitizeCell_));
        existingUrls.add(url);
      }
    });

    if (rowsToAdd.length > 0) {
      insertRowsAtTop_(offersSheet, rowsToAdd);
    }

    const conformingCount = rowsToAdd.filter(function(row) {
      return row[conformityColumn] === CONFORMITY_STATUS.CONFORMING;
    }).length;
    const nonConformingCount = rowsToAdd.filter(function(row) {
      return row[conformityColumn] === CONFORMITY_STATUS.NON_CONFORMING;
    }).length;
    const needsReviewCount = rowsToAdd.length - conformingCount - nonConformingCount;
    insertRefreshLogAtTop_(
      logSheet,
      startedAt,
      new Date(),
      conformingCount,
      nonConformingCount,
      needsReviewCount,
      totalCount
    );
    return createJsonResponse({
      status: "success",
      inserted: rowsToAdd.length,
      conforming: conformingCount,
      non_conforming: nonConformingCount,
      needs_review: needsReviewCount
    });
  } catch (error) {
    return createJsonResponse({ status: "error", message: String(error) });
  } finally {
    if (lockAcquired) {
      lock.releaseLock();
    }
  }
}

function readVehicleCriteria_(spreadsheet) {
  const sheet = spreadsheet.getSheetByName(CRITERIA_SHEET_NAME);
  if (!sheet || sheet.getLastRow() < 2) {
    throw new Error("Onglet ou critères manquants : " + CRITERIA_SHEET_NAME + ".");
  }

  const lastColumn = sheet.getLastColumn();
  const headers = sheet.getRange(1, 1, 1, lastColumn).getDisplayValues()[0]
    .map(normalizeText_);
  const columns = {
    brand: findCriteriaColumn_(headers, ["marque"]),
    models: findCriteriaColumn_(headers, ["modeles", "modele"]),
    budgetMax: findCriteriaColumn_(headers, ["budget max"]),
    mileageMax: findCriteriaColumn_(headers, ["km max"]),
    yearMin: findCriteriaColumn_(headers, ["annee min"]),
    energy: findCriteriaColumn_(headers, ["energie"]),
    seats: findCriteriaColumn_(headers, ["nb places", "nombre de places"]),
    distanceMax: findCriteriaColumn_(headers, ["distance max de besancon", "distance max"]),
    exclusions: findCriteriaColumn_(headers, ["ne pas retenir"])
  };
  Object.keys(columns).forEach(function(key) {
    if (columns[key] < 0) {
      throw new Error("Colonne de critères manquante dans " + CRITERIA_SHEET_NAME + " : " + key + ".");
    }
  });

  const values = sheet.getRange(2, 1, sheet.getLastRow() - 1, lastColumn).getValues();
  const criteria = values.filter(function(row) {
    return String(row[columns.brand] || "").trim() !== "";
  }).map(function(row, index) {
    const parsed = {
      brand: String(row[columns.brand] || "").trim(),
      models: splitCriteriaList_(row[columns.models]),
      budget_max: parseCriteriaNumber_(row[columns.budgetMax]),
      mileage_max: parseCriteriaNumber_(row[columns.mileageMax]),
      year_min: parseCriteriaNumber_(row[columns.yearMin]),
      energy: String(row[columns.energy] || "").trim(),
      seats: parseCriteriaNumber_(row[columns.seats]),
      distance_max_km: parseCriteriaNumber_(row[columns.distanceMax]),
      exclusions: splitCriteriaList_(row[columns.exclusions])
    };
    if (!parsed.models.length || parsed.budget_max === null ||
        parsed.mileage_max === null || parsed.year_min === null ||
        !parsed.energy || parsed.seats === null || parsed.distance_max_km === null) {
      throw new Error("Critères incomplets à la ligne " + (index + 2) + " de " + CRITERIA_SHEET_NAME + ".");
    }
    return parsed;
  });

  if (!criteria.length) {
    throw new Error("Aucun critère véhicule renseigné dans " + CRITERIA_SHEET_NAME + ".");
  }
  return criteria;
}

function findCriteriaColumn_(headers, aliases) {
  return headers.findIndex(function(header) {
    return aliases.some(function(alias) {
      return header === alias || header.indexOf(alias + " ") === 0;
    });
  });
}

function splitCriteriaList_(value) {
  return String(value || "").split(/[,;\n]/).map(function(item) {
    return item.trim();
  }).filter(function(item) {
    return item !== "";
  });
}

function parseCriteriaNumber_(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const normalized = String(value || "").replace(/\s/g, "").replace(/[€]/g, "").replace(",", ".");
  if (!/^-?\d+(?:\.\d+)?$/.test(normalized)) {
    return null;
  }
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeText_(value) {
  return String(value || "").toLowerCase().normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim().replace(/\s+/g, " ");
}

function containsPhrase_(text, phrase) {
  const normalizedText = " " + normalizeText_(text) + " ";
  const normalizedPhrase = normalizeText_(phrase);
  return normalizedPhrase !== "" && normalizedText.indexOf(" " + normalizedPhrase + " ") >= 0;
}

function evaluateVehicleConformity_(row, facts, criteriaRows) {
  if (!facts || typeof facts !== "object" || Array.isArray(facts)) {
    facts = {};
  }
  const evaluations = criteriaRows.map(function(criteria) {
    return evaluateAgainstCriteria_(row, facts, criteria);
  });
  const conforming = evaluations.find(function(result) {
    return result.status === CONFORMITY_STATUS.CONFORMING;
  });
  if (conforming) {
    return conforming;
  }
  const unknowns = evaluations.filter(function(result) {
    return result.status === CONFORMITY_STATUS.NEEDS_REVIEW;
  });
  if (unknowns.length) {
    return {
      status: CONFORMITY_STATUS.NEEDS_REVIEW,
      reasons: uniqueValues_(unknowns.reduce(function(all, result) {
        return all.concat(result.reasons);
      }, []))
    };
  }
  return {
    status: CONFORMITY_STATUS.NON_CONFORMING,
    reasons: uniqueValues_(evaluations.reduce(function(all, result) {
      return all.concat(result.reasons);
    }, []))
  };
}

function evaluateAgainstCriteria_(row, facts, criteria) {
  const reasons = [];
  let hasUnknown = false;
  function check(label, actual, predicate) {
    if (actual === null || actual === undefined || actual === "") {
      hasUnknown = true;
      reasons.push(label + " non renseigné");
    } else if (!predicate(actual)) {
      reasons.push(label + " hors critère");
    }
  }

  const title = String(row[1] || "");
  const details = [title, facts.description, facts.exclusion_text].join(" ");
  const excluded = criteria.exclusions.filter(function(term) {
    return containsPhrase_(details, term);
  });
  if (excluded.length) {
    return {
      status: CONFORMITY_STATUS.NON_CONFORMING,
      reasons: ["Exclusion détectée : " + excluded.join(", ")]
    };
  }

  const make = facts.make || (containsPhrase_(title, criteria.brand) ? criteria.brand : null);
  check("Marque", make, function(value) {
    return normalizeText_(value) === normalizeText_(criteria.brand);
  });

  const model = facts.model || criteria.models.find(function(item) {
    return containsPhrase_(title, item);
  });
  check("Modèle", model, function(value) {
    return criteria.models.some(function(item) {
      return normalizeText_(item) === normalizeText_(value);
    });
  });

  check("Prix", parseCriteriaNumber_(row[2]), function(value) {
    return value <= criteria.budget_max;
  });
  check("Kilométrage", parseCriteriaNumber_(row[3]), function(value) {
    return value <= criteria.mileage_max;
  });
  check("Année", parseCriteriaNumber_(row[4]), function(value) {
    return value >= criteria.year_min;
  });
  check("Énergie", facts.energy, function(value) {
    return normalizeEnergy_(value) === normalizeEnergy_(criteria.energy) ||
      containsPhrase_(value, criteria.energy);
  });
  check("Nombre de places", parseCriteriaNumber_(facts.seats), function(value) {
    return value === criteria.seats;
  });
  check("Distance", parseCriteriaNumber_(row[6]), function(value) {
    return value <= criteria.distance_max_km;
  });

  if (reasons.some(function(reason) {
    return reason.indexOf("hors critère") >= 0;
  })) {
    return { status: CONFORMITY_STATUS.NON_CONFORMING, reasons: reasons };
  }
  return {
    status: hasUnknown ? CONFORMITY_STATUS.NEEDS_REVIEW : CONFORMITY_STATUS.CONFORMING,
    reasons: reasons.length ? reasons : ["Tous les critères vérifiables sont respectés"]
  };
}

function normalizeEnergy_(value) {
  const normalized = normalizeText_(value);
  return normalized.replace(/\bhybrid\b/g, "hybride");
}

function appendConformityReasons_(comment, reasons) {
  const note = "Conformité : " + reasons.join("; ");
  const existing = String(comment || "").trim();
  return existing ? existing + " | " + note : note;
}

function uniqueValues_(values) {
  return values.filter(function(value, index) {
    return values.indexOf(value) === index;
  });
}

function testConformityRules() {
  const headers = [
    "Marque", "Modèles", "Budget_max (€)", "Km_max (Km)", "Année_min",
    "Énergie", "Nb Places", "Distance Max de Besançon (Km)", "Ne pas retenir"
  ];
  const values = [
    "Toyota", "Yaris, Auris, C-HR, C-HR+", 14000, 120000, 2020,
    "Hybride", 5, 350, "2 places, véhicule accidenté"
  ];
  const mockSheet = {
    getLastRow: function() { return 2; },
    getLastColumn: function() { return headers.length; },
    getRange: function(row, column, numberOfRows, numberOfColumns) {
      return {
        getDisplayValues: function() { return [headers]; },
        getValues: function() { return [values]; }
      };
    }
  };
  const parsedCriteria = readVehicleCriteria_({
    getSheetByName: function(name) {
      return name === CRITERIA_SHEET_NAME ? mockSheet : null;
    }
  });
  assertConformityTest_(parsedCriteria.length, 1, "criteria sheet parsing");
  assertConformityTest_(parsedCriteria[0].distance_max_km, 350, "distance header parsing");

  const criteria = [{
    brand: "Toyota",
    models: ["Yaris", "Auris", "C-HR", "C-HR+"],
    budget_max: 14000,
    mileage_max: 120000,
    year_min: 2020,
    energy: "Hybride",
    seats: 5,
    distance_max_km: 350,
    exclusions: ["2 places", "véhicule accidenté"]
  }];
  const baseRow = ["", "Toyota Yaris hybride", 14000, 120000, 2020, "Besançon", 350, "", "", "", "", "", "", "url"];
  const baseFacts = {
    make: "Toyota",
    model: "Yaris",
    energy: "Hybride",
    seats: 5,
    description: "Carnet d'entretien disponible"
  };
  assertConformityTest_(
    evaluateVehicleConformity_(baseRow, baseFacts, criteria).status,
    CONFORMITY_STATUS.CONFORMING,
    "inclusive boundaries"
  );
  assertConformityTest_(
    evaluateVehicleConformity_(baseRow, {}, criteria).status,
    CONFORMITY_STATUS.NEEDS_REVIEW,
    "missing evidence"
  );
  assertConformityTest_(
    evaluateVehicleConformity_(baseRow, Object.assign({}, baseFacts, { seats: 2 }), criteria).status,
    CONFORMITY_STATUS.NON_CONFORMING,
    "wrong number of seats"
  );
  assertConformityTest_(
    evaluateVehicleConformity_(
      baseRow,
      Object.assign({}, baseFacts, { description: "Vendu pour 2 places" }),
      criteria
    ).status,
    CONFORMITY_STATUS.NON_CONFORMING,
    "excluded two-seat description"
  );
  assertConformityTest_(
    evaluateVehicleConformity_(baseRow, Object.assign({}, baseFacts, { description: "Véhicule accidenté" }), criteria).status,
    CONFORMITY_STATUS.NON_CONFORMING,
    "excluded description"
  );
  const aboveBudget = baseRow.slice();
  aboveBudget[2] = 14001;
  assertConformityTest_(
    evaluateVehicleConformity_(aboveBudget, baseFacts, criteria).status,
    CONFORMITY_STATUS.NON_CONFORMING,
    "price above maximum"
  );
  Logger.log("All conformity validation tests passed.");
}

function assertConformityTest_(actual, expected, testName) {
  if (actual !== expected) {
    throw new Error("Conformity test failed (" + testName + "): " + actual + " !== " + expected);
  }
}

function validateSheetColumns_(sheet, name, requiredColumns) {
  if (sheet.getMaxColumns() < requiredColumns) {
    throw new Error("Structure invalide : l'onglet " + name + " doit avoir au moins " + requiredColumns + " colonnes.");
  }
}

function insertRowsAtTop_(sheet, rows) {
  if (!rows || rows.length === 0) {
    return;
  }
  if (sheet.getLastRow() < 2) {
    sheet.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
  } else {
    sheet.insertRowsBefore(2, rows.length);
    sheet.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
  }
}

function sanitizeCell_(value) {
  if (typeof value === "string" && /^[=+\-@]/.test(value)) {
    return "'" + value;
  }
  return value;
}

function insertRefreshLogAtTop_(sheet, startedAt, finishedAt, conformingCount, nonConformingCount, needsReviewCount, totalCount) {
  const timezone = Session.getScriptTimeZone();
  const status = "Terminée - " + conformingCount +
    " annonce(s) conforme(s) ajoutée(s), " + nonConformingCount +
    " non conforme(s), " + needsReviewCount +
    " à vérifier / " + totalCount + " au total.";
  const row = [
    Utilities.formatDate(startedAt, timezone, "dd/MM/yyyy"),
    Utilities.formatDate(startedAt, timezone, "HH:mm"),
    Utilities.formatDate(finishedAt, timezone, "HH:mm"),
    Math.round((finishedAt.getTime() - startedAt.getTime()) / 60000),
    status
  ];
  insertRowsAtTop_(sheet, [row]);
}

function verifyHmacSignature_(secret, body, signature) {
  if (!signature || !/^[a-f0-9]{64}$/i.test(signature)) {
    return false;
  }
  const rawHash = Utilities.computeHmacSha256Signature(body, secret);
  const computedSignature = rawHash.map(function(byte) {
    const value = (byte < 0 ? byte + 256 : byte).toString(16);
    return value.length === 1 ? "0" + value : value;
  }).join("");
  return slowEquals_(computedSignature, signature.toLowerCase());
}

function slowEquals_(left, right) {
  if (left.length !== right.length) {
    return false;
  }
  let difference = 0;
  for (let index = 0; index < left.length; index++) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function createJsonResponse(data) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
