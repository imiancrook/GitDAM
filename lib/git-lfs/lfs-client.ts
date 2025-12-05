export interface LFSPointer {
  version: string;
  oid: string;
  size: number;
}

export interface LFSBatchRequest {
  operation: 'upload' | 'download';
  transfers?: string[];
  ref?: {
    name: string;
  };
  objects: Array<{
    oid: string;
    size: number;
  }>;
}

export interface LFSBatchResponse {
  transfer: string;
  objects: Array<{
    oid: string;
    size: number;
    authenticated?: boolean;
    actions?: {
      upload?: {
        href: string;
        header?: Record<string, string>;
        expires_at?: string;
      };
      download?: {
        href: string;
        header?: Record<string, string>;
        expires_at?: string;
      };
      verify?: {
        href: string;
        header?: Record<string, string>;
      };
    };
    error?: {
      code: number;
      message: string;
    };
  }>;
}

export class LFSClient {
  private baseUrl: string;
  private authToken?: string;

  constructor(baseUrl: string, authToken?: string) {
    this.baseUrl = baseUrl;
    this.authToken = authToken;
  }

  /**
   * Create an LFS pointer file content
   */
  static createPointer(oid: string, size: number): string {
    return `version https://git-lfs.github.com/spec/v1
oid sha256:${oid}
size ${size}
`;
  }

  /**
   * Parse LFS pointer file content
   */
  static parsePointer(content: string): LFSPointer | null {
    const lines = content.trim().split('\n');
    const pointer: Partial<LFSPointer> = {};

    for (const line of lines) {
      if (line.startsWith('version ')) {
        pointer.version = line.substring(8);
      } else if (line.startsWith('oid ')) {
        pointer.oid = line.substring(4);
      } else if (line.startsWith('size ')) {
        pointer.size = parseInt(line.substring(5), 10);
      }
    }

    if (pointer.version && pointer.oid && pointer.size) {
      return pointer as LFSPointer;
    }

    return null;
  }

  /**
   * Check if content is an LFS pointer
   */
  static isLFSPointer(content: string): boolean {
    return content.startsWith('version https://git-lfs.github.com/spec/v1');
  }

  /**
   * Make a batch request to LFS API
   */
  async batch(request: LFSBatchRequest): Promise<LFSBatchResponse> {
    const response = await fetch(`${this.baseUrl}/lfs/objects/batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/vnd.git-lfs+json',
        'Accept': 'application/vnd.git-lfs+json',
        ...(this.authToken && { 'Authorization': `Bearer ${this.authToken}` }),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`LFS batch request failed: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Upload a file using LFS
   */
  async upload(file: File, oid?: string): Promise<string> {
    // Calculate OID if not provided
    const objectId = oid || await this.calculateOID(file);

    // Request upload URL from batch API
    const batchResponse = await this.batch({
      operation: 'upload',
      objects: [
        {
          oid: objectId,
          size: file.size,
        },
      ],
    });

    const object = batchResponse.objects[0];
    if (object.error) {
      throw new Error(`LFS upload failed: ${object.error.message}`);
    }

    if (!object.actions?.upload) {
      throw new Error('No upload action provided by LFS server');
    }

    // Upload file to S3
    const uploadResponse = await fetch(object.actions.upload.href, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/octet-stream',
        ...(object.actions.upload.header || {}),
      },
      body: file,
    });

    if (!uploadResponse.ok) {
      throw new Error(`File upload failed: ${uploadResponse.status} ${uploadResponse.statusText}`);
    }

    return objectId;
  }

  /**
   * Download a file using LFS
   */
  async download(oid: string, size: number): Promise<Blob> {
    // Request download URL from batch API
    const batchResponse = await this.batch({
      operation: 'download',
      objects: [
        {
          oid,
          size,
        },
      ],
    });

    const object = batchResponse.objects[0];
    if (object.error) {
      throw new Error(`LFS download failed: ${object.error.message}`);
    }

    if (!object.actions?.download) {
      throw new Error('No download action provided by LFS server');
    }

    // Download file from S3
    const downloadResponse = await fetch(object.actions.download.href, {
      method: 'GET',
      headers: object.actions.download.header || {},
    });

    if (!downloadResponse.ok) {
      throw new Error(`File download failed: ${downloadResponse.status} ${downloadResponse.statusText}`);
    }

    return downloadResponse.blob();
  }

  /**
   * Calculate OID (SHA256) for a file
   */
  private async calculateOID(file: File): Promise<string> {
    const buffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    return hashHex;
  }
}
