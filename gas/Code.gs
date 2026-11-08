/**
 * @file gas/Code.gs [NEW]
 * @description Backend Google Apps Script (GAS) agissant comme API sécurisée pour la persistance 
 * dans Google Sheets. Implémente la vérification rigoureuse de la signature HMAC-SHA256 
 * et un verrouillage atomique (LockService) pour prévenir toute condition de course.
 */

const SCRIPT_PROP = PropertiesService.getScriptProperties();
const HMAC_SECRET = SCRIPT_PROP.getProperty("HMAC_SECRET");
const TARGET_SHEET_NAME = "Vehicles";

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

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName(TARGET_SHEET_NAME);
    if (!sheet) {
      sheet = ss.insertSheet(TARGET_SHEET_NAME);
      // Initialisation structurée des en-têtes
      sheet.appendRow(["Timestamp", "ID", "Title", "Price", "Mileage", "Year", "URL", "Status"]);
    }

    const timestamp = payload.timestamp ? new Date(payload.timestamp * 1000).toISOString() : new Date().toISOString();
    const rowsToAdd = vehicles.map(v => [
      timestamp,
      v.id || "",
      v.title || "",
      v.price || 0,
      v.mileage || 0,
      v.year || 0,
      v.url || "",
      v.status || "active"
    ]);

    if (rowsToAdd.length > 0) {
      sheet.getRange(sheet.getLastRow() + 1, 1, rowsToAdd.length, rowsToAdd[0].length).setValues(rowsToAdd);
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
