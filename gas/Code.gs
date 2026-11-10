/**
 * Google Apps Script API for the Offres and refresh-log sheets.
 */
const API_SECRET = PropertiesService.getScriptProperties().getProperty("API_SECRET");
const HMAC_SECRET = PropertiesService.getScriptProperties().getProperty("HMAC_SECRET");
const TARGET_SHEET_NAME = "Offres";
const REFRESH_LOG_SHEET_NAME = "Journal";
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
    const values = sourcesSheet.getRange(2, 1, sourcesSheet.getLastRow() - 1, 1).getValues();
    values.forEach(function(row) {
      const target = String(row[0] || "");
      if (target) {
        targets.push(target);
      }
    });
  }

  return createJsonResponse({ status: "success", keys: keys, targets: targets });
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
    const urlColumn = VEHICLE_COLUMNS.indexOf("URL");
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
      const conformity = String(offer[VEHICLE_COLUMNS.indexOf("CONFORME")] || "").trim().toUpperCase();
      if (conformity !== "CONFORME" && conformity !== "NON CONFORME") {
        throw new Error("La colonne CONFORME doit valoir CONFORME ou NON CONFORME.");
      }
      if (!existingUrls.has(url)) {
        rowsToAdd.push(offer.map(sanitizeCell_));
        existingUrls.add(url);
      }
    });

    if (rowsToAdd.length > 0) {
      insertRowsAtTop_(offersSheet, rowsToAdd);
    }

    const conformityColumn = VEHICLE_COLUMNS.indexOf("CONFORME");
    const conformingCount = rowsToAdd.filter(function(row) {
      return String(row[conformityColumn] || "").trim().toUpperCase() === "CONFORME";
    }).length;
    const nonConformingCount = rowsToAdd.length - conformingCount;
    insertRefreshLogAtTop_(logSheet, startedAt, new Date(), conformingCount, nonConformingCount, totalCount);
    return createJsonResponse({ status: "success" });
  } catch (error) {
    return createJsonResponse({ status: "error", message: String(error) });
  } finally {
    if (lockAcquired) {
      lock.releaseLock();
    }
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

function insertRefreshLogAtTop_(sheet, startedAt, finishedAt, conformingCount, nonConformingCount, totalCount) {
  const timezone = Session.getScriptTimeZone();
  const status = "Terminée - " + conformingCount +
    " annonce(s) conforme(s) ajoutée(s), " + nonConformingCount +
    " annonce(s) non conforme(s) ajoutée(s) / " + totalCount + " au total.";
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
