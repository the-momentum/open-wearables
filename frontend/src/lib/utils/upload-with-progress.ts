export type UploadProgressCallback = (progress: number) => void;

interface UploadFormDataOptions {
  headers?: Record<string, string>;
  onProgress?: UploadProgressCallback;
}

interface UploadFormDataResult {
  status: number;
  responseText: string;
}

export function uploadFormDataWithProgress(
  url: string,
  formData: FormData,
  options: UploadFormDataOptions = {}
): Promise<UploadFormDataResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.responseType = 'text';

    if (options.headers) {
      for (const [key, value] of Object.entries(options.headers)) {
        xhr.setRequestHeader(key, value);
      }
    }

    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && options.onProgress) {
        options.onProgress(event.loaded / event.total);
      }
    });

    xhr.addEventListener('load', () => {
      resolve({
        status: xhr.status,
        responseText: xhr.responseText,
      });
    });

    xhr.addEventListener('error', () => {
      reject(new Error('Upload failed due to a network error'));
    });

    xhr.addEventListener('abort', () => {
      reject(new Error('Upload aborted'));
    });

    xhr.send(formData);
  });
}
