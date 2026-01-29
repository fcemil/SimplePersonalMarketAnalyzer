/**
 * IndexedDB wrapper for portfolio transaction storage.
 * 
 * Provides persistent, client-side storage for transaction history.
 * IndexedDB is chosen over localStorage for:
 * - Better performance with large datasets
 * - Structured querying via indexes
 * - No size limitations (unlike 5-10MB localStorage limit)
 * 
 * Database schema:
 * - Database: 'market-analyzer'
 * - Store: 'transactions' with indexes on 'symbol' and 'date'
 * - Key path: 'id' (unique transaction identifier)
 */

const DB_NAME = 'market-analyzer'
const DB_VERSION = 1
const STORE_TX = 'transactions'

/**
 * Open IndexedDB connection and create schema if needed.
 * 
 * @returns {Promise<IDBDatabase>} Database instance
 */
function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    
    // Create object stores and indexes on first open or version upgrade
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_TX)) {
        const store = db.createObjectStore(STORE_TX, { keyPath: 'id' })
        // Create indexes for efficient querying
        store.createIndex('symbol', 'symbol', { unique: false })
        store.createIndex('date', 'date', { unique: false })
      }
    }
    
    request.onerror = () => reject(request.error)
    request.onsuccess = () => resolve(request.result)
  })
}

/**
 * Execute a function with access to the transactions object store.
 * 
 * @param {string} mode - Transaction mode: 'readonly' or 'readwrite'
 * @param {function} run - Function that receives the object store and returns a request
 * @returns {Promise<any>} Result of the database operation
 */
async function withStore(mode, run) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_TX, mode)
    const store = tx.objectStore(STORE_TX)
    const request = run(store)
    
    // Handle operations that don't return a request (e.g., add without caring about result)
    if (!request) {
      tx.oncomplete = () => resolve(undefined)
      tx.onerror = () => reject(tx.error)
      return
    }
    
    // Handle normal request/response operations
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
    tx.onerror = () => reject(tx.error)
  })
}

/**
 * Retrieve all transactions from IndexedDB.
 * 
 * @returns {Promise<Array>} Array of transaction objects
 */
export async function getAllTransactions() {
  return withStore('readonly', (store) => store.getAll())
}

/**
 * Add a new transaction to IndexedDB.
 * 
 * @param {Object} tx - Transaction object with 'id' as primary key
 * @returns {Promise<void>}
 * @throws {Error} If transaction with same id already exists
 */
export async function addTransaction(tx) {
  return withStore('readwrite', (store) => store.add(tx))
}

/**
 * Update an existing transaction in IndexedDB.
 * 
 * @param {Object} tx - Transaction object with 'id' as primary key
 * @returns {Promise<void>}
 * 
 * Note: Creates transaction if it doesn't exist (put vs add)
 */
export async function updateTransaction(tx) {
  return withStore('readwrite', (store) => store.put(tx))
}

/**
 * Delete a transaction from IndexedDB by id.
 * 
 * @param {string} id - Transaction id
 * @returns {Promise<void>}
 */
export async function deleteTransaction(id) {
  return withStore('readwrite', (store) => store.delete(id))
}
