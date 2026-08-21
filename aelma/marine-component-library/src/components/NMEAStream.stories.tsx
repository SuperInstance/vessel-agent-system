import type { Meta, StoryObj } from '@storybook/react';
import { NMEAStream } from './NMEAStream';
import { dayTheme, nightTheme } from '../types/theme';
import type { NMEASentence } from '../types/vessel';

const meta: Meta<typeof NMEAStream> = {
  title: 'Marine Components/NMEAStream',
  component: NMEAStream,
  tags: ['autodocs'],
  argTypes: {
    className: { control: 'text' },
    maxVisible: { control: 'number' },
    autoScroll: { control: 'boolean' },
    showTimestamp: { control: 'boolean' },
    showChecksum: { control: 'boolean' },
    compact: { control: 'boolean' },
  },
};

export default meta;
type Story = StoryObj<typeof NMEAStream>;

// Mock NMEA sentences
const mockSentences: NMEASentence[] = [
  {
    type: 'GPGGA',
    raw: '$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47',
    timestamp_ns: BigInt(Date.now() * 1e6),
    valid: true,
    checksum_valid: true,
    parsed: {
      time: '12:35:19',
      lat: '4807.038',
      lat_dir: 'N',
      lon: '01131.000',
      lon_dir: 'E',
      quality: 1,
      num_sats: 8,
      hdop: 0.9,
      altitude: 545.4,
      altitude_units: 'M',
    },
  },
  {
    type: 'GPRMC',
    raw: '$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,,,A*06',
    timestamp_ns: BigInt((Date.now() - 1000) * 1e6),
    valid: true,
    checksum_valid: true,
    parsed: {
      time: '12:35:19',
      status: 'A',
      lat: '4807.038',
      lat_dir: 'N',
      lon: '01131.000',
      lon_dir: 'E',
      speed_kn: 22.4,
      track_true: 84.4,
      date: '230394',
    },
  },
  {
    type: 'GPVTG',
    raw: '$GPVTG,084.4,T,084.4,M,022.4,N,041.6,K*50',
    timestamp_ns: BigInt((Date.now() - 2000) * 1e6),
    valid: true,
    checksum_valid: true,
    parsed: {
      track_true: 84.4,
      track_mag: 84.4,
      speed_kn: 22.4,
      speed_kmh: 41.6,
    },
  },
  {
    type: 'GPGSA',
    raw: '$GPGSA,A,3,04,05,,09,12,,,24,,,,,2.5,1.3,2.1*39',
    timestamp_ns: BigInt((Date.now() - 3000) * 1e6),
    valid: true,
    checksum_valid: true,
    parsed: {
      mode: 'A',
      fix_type: 3,
      pdop: 2.5,
      hdop: 1.3,
      vdop: 2.1,
    },
  },
  {
    type: 'INVALID',
    raw: '$INVALID,SENTENCE*FF',
    timestamp_ns: BigInt((Date.now() - 4000) * 1e6),
    valid: false,
    checksum_valid: false,
  },
  {
    type: 'GPGGA',
    raw: '$GPGGA,123520,4807.040,N,01131.005,E,1,09,0.8,546.2,M,46.9,M,,*48',
    timestamp_ns: BigInt((Date.now() - 5000) * 1e6),
    valid: true,
    checksum_valid: true,
    parsed: {
      time: '12:35:20',
      lat: '4807.040',
      lat_dir: 'N',
      lon: '01131.005',
      lon_dir: 'E',
      quality: 1,
      num_sats: 9,
      hdop: 0.8,
      altitude: 546.2,
      altitude_units: 'M',
    },
  },
];

export const DayMode: Story = {
  args: {
    sentences: mockSentences,
    theme: dayTheme,
    maxVisible: 100,
    autoScroll: true,
    showTimestamp: true,
    showChecksum: true,
    compact: false,
  },
};

export const NightMode: Story = {
  args: {
    sentences: mockSentences,
    theme: nightTheme,
    maxVisible: 100,
    autoScroll: true,
  },
  parameters: {
    theme: 'night',
  },
};

export const Compact: Story = {
  args: {
    sentences: mockSentences,
    theme: dayTheme,
    compact: true,
  },
};

export const Filtered: Story = {
  args: {
    sentences: mockSentences,
    theme: dayTheme,
    filterTypes: ['GPGGA', 'GPRMC'],
  },
};

export const Highlighted: Story = {
  args: {
    sentences: mockSentences,
    theme: dayTheme,
    highlightRules: [/ALARM/, /ERROR/, /INVALID/],
  },
};

export const NoTimestamp: Story = {
  args: {
    sentences: mockSentences,
    theme: dayTheme,
    showTimestamp: false,
  },
};

export const NoChecksum: Story = {
  args: {
    sentences: mockSentences,
    theme: dayTheme,
    showChecksum: false,
  },
};

export const Limited: Story = {
  args: {
    sentences: mockSentences,
    theme: dayTheme,
    maxVisible: 3,
  },
};

export const NoAutoScroll: Story = {
  args: {
    sentences: mockSentences,
    theme: dayTheme,
    autoScroll: false,
  },
};

export const Empty: Story = {
  args: {
    sentences: [],
    theme: dayTheme,
  },
};

export const Interactive: Story = {
  args: {
    sentences: mockSentences,
    theme: dayTheme,
  },
  parameters: {
    actions: {
      handles: ['onSentenceClick'],
    },
  },
};
