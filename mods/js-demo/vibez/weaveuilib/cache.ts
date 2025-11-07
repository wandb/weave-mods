export async function createIndexedDBMemoizer<TArgs extends any[], TResult>(
  dbName: string,
  storeName: string
): Promise<
  (
    fn: (...args: TArgs) => Promise<TResult>
  ) => (...args: TArgs) => Promise<TResult>
> {
  const db = await openIndexedDB(dbName, storeName);

  return function memoize(
    fn: (...args: TArgs) => Promise<TResult>
  ): (...args: TArgs) => Promise<TResult> {
    return async function (...args: TArgs): Promise<TResult> {
      const key = JSON.stringify(args);

      // Check if the result is already in the database
      // const cachedResult = await getFromDB<TResult>(db, storeName, key);
      // if (cachedResult !== undefined) {
      //   return cachedResult;
      // }

      // If not, call the original function
      const result = await fn(...args);

      // Store the result in the database
      await putInDB(db, storeName, key, result);

      return result;
    };
  };
}

async function openIndexedDB(
  dbName: string,
  storeName: string
): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(dbName);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(storeName)) {
        db.createObjectStore(storeName);
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getFromDB<T>(
  db: IDBDatabase,
  storeName: string,
  key: string
): Promise<T | undefined> {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(storeName, "readonly");
    const store = transaction.objectStore(storeName);
    const request = store.get(key);

    request.onsuccess = () => resolve(request.result as T | undefined);
    request.onerror = () => reject(request.error);
  });
}

async function putInDB<T>(
  db: IDBDatabase,
  storeName: string,
  key: string,
  value: T
): Promise<void> {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(storeName, "readwrite");
    const store = transaction.objectStore(storeName);
    const request = store.put(value, key);

    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function clearDB(db: IDBDatabase, storeName: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(storeName, "readwrite");
    const store = transaction.objectStore(storeName);
    const request = store.clear();

    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

export async function clearCache(
  dbName: string,
  storeName: string
): Promise<void> {
  const db = await openIndexedDB(dbName, storeName);
  await clearDB(db, storeName);
  db.close();
}

// // Usage Example
// (async () => {
//   // Create the memoizer
//   const memoize = await createIndexedDBMemoizer<[number], number>(
//     "MyMemoDB",
//     "MemoStore"
//   );

//   // Define a slow asynchronous function
//   const slowFn = async (num: number): Promise<number> => {
//     console.log(`Computing for ${num}...`);
//     return new Promise((resolve) => setTimeout(() => resolve(num * 2), 1000));
//   };

//   // Memoize the function
//   const memoizedFn = memoize(slowFn);

//   // Call the memoized function
//   console.log(await memoizedFn(5)); // Computes and caches
//   console.log(await memoizedFn(5)); // Fetches from cache
// })();
