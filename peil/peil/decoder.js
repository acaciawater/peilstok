/**
 * Decoder peilstok messages from Untung Haryono <untung@twtg.io>
 */

function Decoder(bytes, port) {
  if(bytes[0] == 0) {
    var decoded = {
      type: bytes[0],
      message: "ERROR"
    }
  } else if(bytes[0] == 1) {
    var decoded = {
      type: bytes[0],
      position: bytes[1],
      /*
      //total_modules: bytes[17],
      year: (bytes[11] << 8) | bytes[10],
      month: bytes[12],
      day: bytes[13],
      hour: bytes[14],
      min: bytes[15],
      sec: bytes[16],
      time: ((bytes[16] ) + (bytes[15])* 10000) + (bytes[14] * 1000000) + (bytes[13] * 100000000) + (bytes[12]  * 10000000000) + (((bytes[11] << 8) | bytes[10])* 1000000000000),
      */
      latitude: (bytes[5] << 24) | (bytes[4] << 16)  | (bytes[3] << 8) | bytes[2],
      longitude: (bytes[9] << 24) | (bytes[8] << 16)  | (bytes[7] << 8) | bytes[6],
      height: (bytes[13] << 24) | (bytes[12] << 16)  | (bytes[11] << 8) | bytes[10],
      hMSL: (bytes[17] << 24) | (bytes[16] << 16)  | (bytes[15] << 8) | bytes[14],
      hAcc: (bytes[21] << 24) | (bytes[20] << 16)  | (bytes[19] << 8) | bytes[18],
      vAcc: (bytes[25] << 24) | (bytes[24] << 16)  | (bytes[23] << 8) | bytes[22],
      /*
      //battery: (bytes[35] << 8) | bytes[34], 
      //pressure: (bytes[37] << 8) | bytes[36]
      */
    };
  } else if(bytes[0] == 2) {
    var decoded = {
      type: bytes[0],
      position: bytes[1],
      temperature: (bytes[3] << 8) | bytes[2],
      ec1: (bytes[5] << 8) | bytes[4],
      ec2: (bytes[7] << 8) | bytes[6]
    };
  } else if(bytes[0] == 3) {
    var decoded = {
      type: bytes[0],
      position: bytes[1],
      pressure: (bytes[3] << 8) | bytes[2]
    };
  } else if(bytes[0] == 4) {
    var decoded = {
      type: bytes[0],
      position: bytes[1],
      total_modules: bytes[17],
      time: (((bytes[16] << 8) | bytes[15]) * 10000000000) + (bytes[14] * 100000000) + (bytes[13] * 1000000) + (bytes[12] * 10000) + (bytes[11] * 100) + (bytes[10] * 1),
      latitude: (bytes[5] << 24) | (bytes[4] << 16)  | (bytes[3] << 8) | bytes[2],
      longitude: (bytes[9] << 24) | (bytes[8] << 16)  | (bytes[7] << 8) | bytes[6]
    };
  } else if(bytes[0] == 5) {
    var decoded = {
      type: bytes[0],
      position: bytes[1],
      angle: (bytes[3] << 8) | bytes[2]
    };
  } else if(bytes[0] == 6) {
    var decoded = {
      type: bytes[0],
      position: bytes[1],
      total: bytes[2],
      battery: (bytes[4] << 8) | bytes[3], 
      pressure: (bytes[6] << 8) | bytes[5],
      angle: (bytes[8] << 8) | bytes[7]
    }
  } else if(bytes[0] == 7) {
    var decoded = {
      type: bytes[0],
      message: "ERROR"
    }
  } else {
    var decoded = {
      type: byte[0]
    }
  }
  return decoded;
}
