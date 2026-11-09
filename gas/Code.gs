/**
 * @file gas/Code.gs [NEW]
 * @description Backend Google Apps Script (GAS) agissant comme API sécurisée pour la persistance 
 * dans Google Sheets. Implémente la vérification rigoureuse de la signature HMAC-SHA256 
 * et un verrouillage atomique (LockService) pour prévenir toute condition de course.
 */

const SCRIPT_PROP = PropertiesService.getScriptProperties();
const API_SECRET = SCRIPT_PROP.getProperty("API_SECRET");
const HMAC_SECRET = SCRIPT_PROP.getProperty("HMAC_SECRET");
const TARGET_SHEET_NAME = "Vehicles";
const VEHICLE_COLUMNS = [
  "Date", "Title", "Price", "Mileage", "Year", "City", "Dist.", "Notebook",
  "Conformity", "Risk", "Comment", "Seller", "Source", "URL"
];

// Ligne de référence fournie pour test, dans l'ordre des 14 colonnes :
// 29/09/2026 | ToyTest yaya | 9999 | 99999 | 0 | MaVille | 999 | NC |
// TESTCONFORME | AlerteRisque | Commentaire | TESTAUTO | SOURCETEST |
// https://www.testsite.fr/ad/voitures/3206865999

function doGet(e) {
  if (!API_SECRET) {
    return createJsonResponse({ status: "error", message: "Server configuration error: API_SECRET not set." }, 500);
  }

  const requestSecret = e && e.parameter ? e.parameter.secret || "" : "";
  if (!slowEquals_(API_SECRET, requestSecret)) {
    return createJsonResponse({ status: "error", message: "Unauthorized: Invalid or missing API secret." }, 401);
  }

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(TARGET_SHEET_NAME);
  const keys = [];
  if (sheet && sheet.getLastRow() > 1) {
    const urlColumn = VEHICLE_COLUMNS.indexOf("URL") + 1;
    const values = sheet.getRange(2, urlColumn, sheet.getLastRow() - 1, 1).getDisplayValues();
    values.forEach(function(row) {
      if (row[0]) {
        keys.push(row[0]);
      }
    });
  }

  return createJsonResponse({ status: "success", keys: keys });
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  
  try {
    // Acquisition du verrou atomique (timeout de 30 secondes pour éviter les blocages en cascade)
    if (!lock.tryLock(30000)) {
      return createJsonResponse({ status: "error", message: "Concurrency lock timeout exceeded." }, 429);
    }

    if (!e || !e.postData || !e.postData.contents) {
      return createJsonResponse({ status: "error", message: "Missing or empty request body." }, 400);
    }

    const rawBody = e.postData.contents;
    const headers = e.headers || {};
    const hmacHeader = headers["X-Hub-Signature-256"] || headers["x-hub-signature-256"] || "";

    if (!HMAC_SECRET) {
      return createJsonResponse({ status: "error", message: "Server configuration error: HMAC_SECRET not set." }, 500);
    }

    // Validation cryptographique de la signature HMAC-SHA256
    if (!verifyHmacSignature_(HMAC_SECRET, rawBody, hmacHeader)) {
      return createJsonResponse({ status: "error", message: "Unauthorized: Invalid or missing HMAC signature." }, 401);
    }

    const payload = JSON.parse(rawBody);
    const vehicles = payload.vehicles || [];
    if (!Array.isArray(vehicles)) {
      return createJsonResponse({ status: "error", message: "Invalid vehicles payload: expected an array." }, 400);
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName(TARGET_SHEET_NAME);
    if (!sheet) {
      sheet = ss.insertSheet(TARGET_SHEET_NAME);
      sheet.appendRow(VEHICLE_COLUMNS);
    }

    const timestamp = payload.timestamp ? new Date(payload.timestamp * 1000).toISOString() : new Date().toISOString();
    const rowsToAdd = vehicles.map(function(vehicle) {
      if (Array.isArray(vehicle)) {
        if (vehicle.length !== VEHICLE_COLUMNS.length) {
          throw new Error("Invalid vehicle row: expected exactly 14 columns.");
        }
        return vehicle;
      }
      if (!vehicle || typeof vehicle !== "object") {
        throw new Error("Invalid vehicle: expected an object or a 14-column array.");
      }
      return [
        vehicle.date !== undefined ? vehicle.date : timestamp,
        vehicle.title !== undefined ? vehicle.title : "",
        vehicle.price !== undefined ? vehicle.price : 0,
        vehicle.mileage !== undefined ? vehicle.mileage : 0,
        vehicle.year !== undefined ? vehicle.year : 0,
        vehicle.city !== undefined ? vehicle.city : "",
        vehicle.distance !== undefined ? vehicle.distance : "",
        vehicle.notebook !== undefined ? vehicle.notebook : "",
        vehicle.conformity !== undefined ? vehicle.conformity : "",
        vehicle.risk !== undefined ? vehicle.risk : "",
        vehicle.comment !== undefined ? vehicle.comment : "",
        vehicle.seller !== undefined ? vehicle.seller : "",
        vehicle.source !== undefined ? vehicle.source : "",
        vehicle.url !== undefined ? vehicle.url : ""
      ];
    });

    if (rowsToAdd.length > 0) {
      if (sheet.getMaxColumns() < VEHICLE_COLUMNS.length) {
        sheet.insertColumnsAfter(sheet.getMaxColumns(), VEHICLE_COLUMNS.length - sheet.getMaxColumns());
      }
      sheet.getRange(sheet.getLastRow() + 1, 1, rowsToAdd.length, VEHICLE_COLUMNS.length).setValues(rowsToAdd);
    }

    return createJsonResponse({ status: "success", inserted_count: rowsToAdd.length });

  } catch (err) {
    return createJsonResponse({ status: "error", message: err.toString() }, 500);
  } finally {
    lock.releaseLock();
  }
}

function verifyHmacSignature_(secret, body, signatureHeader) {
  if (!signatureHeader || !signatureHeader.startsWith("sha256=")) {
    return false;
  }
  const receivedSig = signatureHeader.replace("sha256=", "");
  
  const rawHash = Utilities.computeHmacSha256Signature(body, secret);
  const computedSig = rawHash.map(function(byte) {
    var v = (byte < 0 ? byte + 256 : byte).toString(16);
    return v.length == 1 ? "0" + v : v;
  }).join("");

  // Comparaison en temps constant pour contrer les attaques temporelles (timing attacks)
  return slowEquals_(computedSig, receivedSig);
}

function slowEquals_(a, b) {
  if (a.length !== b.length) {
    return false;
  }
  var out = 0;
  for (var i = 0; i < a.length; i++) {
    out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return out === 0;
}

function createJsonResponse(data, statusCode) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
