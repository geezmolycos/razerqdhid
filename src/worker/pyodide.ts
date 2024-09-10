import { loadPyodide, PyodideInterface } from 'pyodide';
import * as Comlink from "comlink";
import {syncExpose} from "comsync";

async function initPyodide() {
  let pyodide = await loadPyodide({
    indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/',
  });
  const py_files = 'webhid.py qdrazer/device.py qdrazer/protocol.py basilisk_v3/device.py';
  await pyodide.runPythonAsync(`
    from pyodide.http import pyfetch
    from asyncio import gather
    import os
    def safe_open_wb(path):
      ''' Open "path" for writing, creating any parent directories as needed.
      '''
      p = os.path.dirname(path)
      if p:
        os.makedirs(p, exist_ok=True)
      return open(path, 'wb')
    async def fetch_py(root, filename):
      print(f'fetching py file {filename}')
      response = await pyfetch(root + filename)
      with safe_open_wb(filename) as f:
        f.write(await response.bytes())
  
    py_files = '${py_files}'
    py_files = py_files.split(' ')
    await gather(*[fetch_py('${import.meta.env.BASE_URL}' + 'py/', fn) for fn in py_files])
  `);
  await pyodide.runPythonAsync(`
    import shutil
    shutil.copy('webhid.py', 'hid.py')
  `);
  await pyodide.runPythonAsync('import hid');
  return pyodide;
}

var pyodide: PyodideInterface | null = null;
type NotifyCallback = (name: string, ...args: any[]) => any;

Comlink.expose({
  init: async () => {
    pyodide = await initPyodide();
  },
  setStdout: (notifyCallback: NotifyCallback) => {
    if (pyodide === null) {
      throw new Error('pyodide is not initialized');
    }
    pyodide.setStdout({batched: (str) => notifyCallback('print', str)});
  },
  runPython: syncExpose((syncExtras, code, options, notifyCallback: NotifyCallback) => {
    if (pyodide === null) {
      throw new Error('pyodide is not initialized');
    }
    const await_js = (code: string) => {
      notifyCallback('await_js', code);
      const result = syncExtras.readMessage();
      return result;
    }
    options = options ?? {};
    options.globals = options.globals ?? pyodide.toPy({});
    options.globals.set('syncExtras', syncExtras);
    options.globals.set('notifyCallback', notifyCallback);
    options.globals.set('await_js', await_js);
    return pyodide.runPython(code, options);
  }),
  runTest: syncExpose((syncExtras, notifyCallback) => {
    notifyCallback('world');
    let m = syncExtras.readMessage();
    notifyCallback('hello');
    m = syncExtras.readMessage();
  }),
});
