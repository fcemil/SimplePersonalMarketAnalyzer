const DB_NAME = 'market-analyzer'
const DB_VERSION = 1
const STORE_TX = 'transactions'

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_TX)) {
        const store = db.createObjectStore(STORE_TX, { keyPath: 'id' })
        store.createIndex('symbol', 'symbol', { unique: false })
        store.createIndex('date', 'date', { unique: false })
      }
    }
    request.onerror = () => reject(request.error)
    request.onsuccess = () => resolve(request.result)
  })
}

async function withStore(mode, run) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_TX, mode)
    const store = tx.objectStore(STORE_TX)
    const request = run(store)
    if (!request) {
      tx.oncomplete = () => resolve(undefined)
      tx.onerror = () => reject(tx.error)
      return
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
    tx.onerror = () => reject(tx.error)
  })
}

export async function getAllTransactions() {
  return withStore('readonly', (store) => store.getAll())
}

export async function addTransaction(tx) {
  return withStore('readwrite', (store) => store.add(tx))
}

export async function updateTransaction(tx) {
  return withStore('readwrite', (store) => store.put(tx))
}

export async function deleteTransaction(id) {
  return withStore('readwrite', (store) => store.delete(id))
}
